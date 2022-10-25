#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file: py_redis_lock.py
# @time: 2021-10-30 22:35
# @author: jack
# @Email:793936517@qq.com
# @desc:

import sys
import threading
import weakref
from base64 import b64encode
from logging import getLogger
from os import urandom

from redis import StrictRedis

__version__ = '3.6.0'

logger = getLogger(__name__)

text_type = str
binary_type = bytes


# Check if the id match. If not, return an error code.
UNLOCK_SCRIPT = b"""
    if redis.call("get", KEYS[1]) ~= ARGV[1] then
        return 1
    else
        redis.call("del", KEYS[2])
        redis.call("lpush", KEYS[2], 1)
        redis.call("pexpire", KEYS[2], ARGV[2])
        redis.call("del", KEYS[1])
        return 0
    end
"""

# Covers both cases when key doesn't exist and doesn't equal to lock's id
EXTEND_SCRIPT = b"""
    if redis.call("get", KEYS[1]) ~= ARGV[1] then
        return 1
    elseif redis.call("ttl", KEYS[1]) < 0 then
        return 2
    else
        redis.call("expire", KEYS[1], ARGV[2])
        return 0
    end
"""

RESET_SCRIPT = b"""
    redis.call('del', KEYS[2])
    redis.call('lpush', KEYS[2], 1)
    redis.call('pexpire', KEYS[2], ARGV[2])
    return redis.call('del', KEYS[1])
"""

RESET_ALL_SCRIPT = b"""
    local locks = redis.call('keys', 'lock:*')
    local signal
    for _, lock in pairs(locks) do
        signal = 'lock-signal:' .. string.sub(lock, 6)
        redis.call('del', signal)
        redis.call('lpush', signal, 1)
        redis.call('expire', signal, 1)
        redis.call('del', lock)
    end
    return #locks
"""


class AlreadyAcquired(RuntimeError):
    pass


class NotAcquired(RuntimeError):
    pass


class AlreadyStarted(RuntimeError):
    pass


class TimeoutNotUsable(RuntimeError):
    pass


class InvalidTimeout(RuntimeError):
    pass


class TimeoutTooLarge(RuntimeError):
    pass


class NotExpirable(RuntimeError):
    pass


class Lock(object):
    """
    A Lock context manager implemented via redis SETNX/BLPOP.
    """
    unlock_script = None
    extend_script = None
    reset_script = None
    reset_all_script = None

    def __init__(self, redis_client, name, expire=None, id=None, auto_renewal=False, strict=True, signal_expire=1000):
        """
        :param redis_client:
            An instance of :class:`~StrictRedis`.
        :param name:
            The name (redis key) the lock should have.
        :param expire:
            The lock expiry time in seconds. If left at the default (None)
            the lock will not expire.
        :param id:
            The ID (redis value) the lock should have. A random value is
            generated when left at the default.
            Note that if you specify this then the lock is marked as "held". Acquires
            won't be possible.
        :param auto_renewal:
            If set to ``True``, Lock will automatically renew the lock so that it
            doesn't expire for as long as the lock is held (acquire() called
            or running in a context manager).
            Implementation note: Renewal will happen using a daemon thread with
            an interval of ``expire*2/3``. If wishing to use a different renewal
            time, subclass Lock, call ``super().__init__()`` then set
            ``self._lock_renewal_interval`` to your desired interval.
        :param strict:
            If set ``True`` then the ``redis_client`` needs to be an instance of ``redis.StrictRedis``.
        :param signal_expire:
            Advanced option to override signal list expiration in milliseconds. Increase it for very slow clients. Default: ``1000``.
        """
        if strict and not isinstance(redis_client, StrictRedis):
            raise ValueError("redis_client must be instance of StrictRedis. "
                             "Use strict=False if you know what you're doing.")
        if auto_renewal and expire is None:
            raise ValueError("Expire may not be None when auto_renewal is set")

        self._client = redis_client

        if expire:
            expire = int(expire)
            if expire < 0:
                raise ValueError("A negative expire is not acceptable.")
        else:
            expire = None
        self._expire = expire

        self._signal_expire = signal_expire
        if id is None:
            self._id = b64encode(urandom(18)).decode('ascii')
        elif isinstance(id, binary_type):
            try:
                self._id = id.decode('ascii')
            except UnicodeDecodeError:
                self._id = b64encode(id).decode('ascii')
        elif isinstance(id, text_type):
            self._id = id
        else:
            raise TypeError("Incorrect type for `id`. Must be bytes/str not %s." % type(id))
        self._name = 'lock:' + name
        self._signal = 'lock-signal:' + name
        self._lock_renewal_interval = (float(expire) * 2 / 3
                                       if auto_renewal
                                       else None)
        self._lock_renewal_thread = None

        self.register_scripts(redis_client)

    @classmethod
    def register_scripts(cls, redis_client):
        global reset_all_script
        if reset_all_script is None:
            reset_all_script = redis_client.register_script(RESET_ALL_SCRIPT)
            cls.unlock_script = redis_client.register_script(UNLOCK_SCRIPT)
            cls.extend_script = redis_client.register_script(EXTEND_SCRIPT)
            cls.reset_script = redis_client.register_script(RESET_SCRIPT)
            cls.reset_all_script = redis_client.register_script(RESET_ALL_SCRIPT)

    @property
    def _held(self):
        return self.id == self.get_owner_id()

    def reset(self):
        """
        Forcibly deletes the lock. Use this with care.
        """
        self.reset_script(client=self._client, keys=(self._name, self._signal), args=(self.id, self._signal_expire))

    @property
    def id(self):
        return self._id

    def get_owner_id(self):
        owner_id = self._client.get(self._name)
        if isinstance(owner_id, binary_type):
            owner_id = owner_id.decode('ascii', 'replace')
        return owner_id

    def acquire(self, blocking=True, timeout=None):
        """
        :param blocking:
            Boolean value specifying whether lock should be blocking or not.
        :param timeout:
            An integer value specifying the maximum number of seconds to block.
        """
        logger.debug("Getting %r ...", self._name)

        if self._held:
            raise AlreadyAcquired("Already acquired from this Lock instance.")

        if not blocking and timeout is not None:
            raise TimeoutNotUsable("Timeout cannot be used if blocking=False")

        if timeout:
            timeout = int(timeout)
            if timeout < 0:
                raise InvalidTimeout("Timeout (%d) cannot be less than or equal to 0" % timeout)

            if self._expire and not self._lock_renewal_interval and timeout > self._expire:
                raise TimeoutTooLarge("Timeout (%d) cannot be greater than expire (%d)" % (timeout, self._expire))

        busy = True
        blpop_timeout = timeout or self._expire or 0
        timed_out = False
        while busy:
            busy = not self._client.set(self._name, self._id, nx=True, ex=self._expire)
            if busy:
                if timed_out:
                    return False
                elif blocking:
                    timed_out = not self._client.blpop(self._signal, blpop_timeout) and timeout
                else:
                    logger.debug("Failed to get %r.", self._name)
                    return False
        #是否应该取刷新过期时间，不是一定要这样做， 这是有风险， 如果当前的进程没有挂，但是一直阻塞，退不出来，就会永远续租
        logger.debug("Got lock for %r.", self._name)
        if self._lock_renewal_interval is not None:
            self._start_lock_renewer()
        return True

    def extend(self, expire=None):
        """Extends expiration time of the lock.
        :param expire:
            New expiration time. If ``None`` - `expire` provided during
            lock initialization will be taken.
        """
        if expire:
            expire = int(expire)
            if expire < 0:
                raise ValueError("A negative expire is not acceptable.")
        elif self._expire is not None:
            expire = self._expire
        else:
            raise TypeError(
                "To extend a lock 'expire' must be provided as an "
                "argument to extend() method or at initialization time."
            )

        error = self.extend_script(client=self._client, keys=(self._name, self._signal), args=(self._id, expire))
        if error == 1:
            raise NotAcquired("Lock %s is not acquired or it already expired." % self._name)
        elif error == 2:
            raise NotExpirable("Lock %s has no assigned expiration time" % self._name)
        elif error:
            raise RuntimeError("Unsupported error code %s from EXTEND script" % error)

    @staticmethod
    def _lock_renewer(lockref, interval, stop):
        """
        Renew the lock key in redis every `interval` seconds for as long
        as `self._lock_renewal_thread.should_exit` is False.
        """
        log = getLogger("%s.lock_refresher" % __name__)
        while not stop.wait(timeout=interval):
            log.debug("Refreshing lock")
            lock = lockref()
            if lock is None:
                log.debug("The lock no longer exists, "
                          "stopping lock refreshing")
                break
            lock.extend(expire=lock._expire)
            del lock
        log.debug("Exit requested, stopping lock refreshing")

    def _start_lock_renewer(self):
        """
        Starts the lock refresher thread.
        """
        if self._lock_renewal_thread is not None:
            raise AlreadyStarted("Lock refresh thread already started")

        logger.debug(
            "Starting thread to refresh lock every %s seconds",
            self._lock_renewal_interval
        )
        self._lock_renewal_stop = threading.Event()
        self._lock_renewal_thread = threading.Thread(
            group=None,
            target=self._lock_renewer,
            kwargs={'lockref': weakref.ref(self),
                    'interval': self._lock_renewal_interval,
                    'stop': self._lock_renewal_stop}
        )
        self._lock_renewal_thread.setDaemon(True)
        self._lock_renewal_thread.start()

    def _stop_lock_renewer(self):
        """
        Stop the lock renewer.
        This signals the renewal thread and waits for its exit.
        """
        if self._lock_renewal_thread is None or not self._lock_renewal_thread.is_alive():
            return
        logger.debug("Signalling the lock refresher to stop")
        self._lock_renewal_stop.set()
        self._lock_renewal_thread.join()
        self._lock_renewal_thread = None
        logger.debug("Lock refresher has stopped")

    def __enter__(self): #用来使用with语句
        acquired = self.acquire(blocking=True)
        assert acquired, "Lock wasn't acquired, but blocking=True"
        return self

    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        self.release()

    def release(self):
        """Releases the lock, that was acquired with the same object.
        .. note::
            If you want to release a lock that you acquired in a different place you have two choices:
            * Use ``Lock("name", id=id_from_other_place).release()``
            * Use ``Lock("name").reset()``
        """
        if self._lock_renewal_thread is not None:
            self._stop_lock_renewer()
        logger.debug("Releasing %r.", self._name)
        error = self.unlock_script(client=self._client, keys=(self._name, self._signal), args=(self._id, self._signal_expire))
        if error == 1:
            raise NotAcquired("Lock %s is not acquired or it already expired." % self._name)
        elif error:
            raise RuntimeError("Unsupported error code %s from EXTEND script." % error)

    def locked(self):
        """
        Return true if the lock is acquired.
        Checks that lock with same name already exists. This method returns true, even if
        lock have another id.
        """
        return self._client.exists(self._name) == 1


reset_all_script = None


def reset_all(redis_client):
    """
    Forcibly deletes all locks if its remains (like a crash reason). Use this with care.
    :param redis_client:
        An instance of :class:`~StrictRedis`.
    """
    Lock.register_scripts(redis_client)

    reset_all_script(client=redis_client)  # noqa