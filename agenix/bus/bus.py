"""Async message bus for decoupled service communication."""

import asyncio
from typing import Callable, Awaitable

from .events import Event, AgentMessageEvent, CronJobEvent, HeartbeatEvent


class MessageBus:
    """
    Async event bus that decouples services from the agent core.

    Services (cron, heartbeat) publish events to the bus, and consumers
    (agent, UI) subscribe to events they care about.
    """

    def __init__(self):
        """Initialize the message bus."""
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers: dict[str, list[Callable[[Event], Awaitable[None]]]] = {}
        self._running = False
        self._dispatch_task: asyncio.Task | None = None

    async def publish(self, event: Event) -> None:
        """
        Publish an event to the bus.

        Args:
            event: Event to publish
        """
        await self.queue.put(event)

    def subscribe(
        self,
        event_kind: str,
        callback: Callable[[Event], Awaitable[None]]
    ) -> None:
        """
        Subscribe to events of a specific kind.

        Args:
            event_kind: Event kind to subscribe to (e.g., "cron_job", "heartbeat", "*" for all)
            callback: Async callback function to handle the event
        """
        if event_kind not in self._subscribers:
            self._subscribers[event_kind] = []
        self._subscribers[event_kind].append(callback)

    def unsubscribe(
        self,
        event_kind: str,
        callback: Callable[[Event], Awaitable[None]]
    ) -> None:
        """
        Unsubscribe from events.

        Args:
            event_kind: Event kind to unsubscribe from
            callback: Callback function to remove
        """
        if event_kind in self._subscribers:
            self._subscribers[event_kind] = [
                cb for cb in self._subscribers[event_kind] if cb != callback
            ]

    async def start(self) -> None:
        """Start the message bus dispatcher."""
        if self._running:
            return

        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        print("Message bus started")

    def stop(self) -> None:
        """Stop the message bus dispatcher."""
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            self._dispatch_task = None
        print("Message bus stopped")

    async def _dispatch_loop(self) -> None:
        """
        Dispatch loop that processes events from the queue.
        Runs as a background task.
        """
        while self._running:
            try:
                # Wait for event with timeout to allow graceful shutdown
                event = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in dispatch loop: {e}")

    async def _dispatch_event(self, event: Event) -> None:
        """
        Dispatch event to all subscribers.

        Args:
            event: Event to dispatch
        """
        event_kind = event.kind

        # Dispatch to specific subscribers
        subscribers = self._subscribers.get(event_kind, [])

        # Also dispatch to wildcard subscribers
        subscribers.extend(self._subscribers.get("*", []))

        # Call all subscribers
        for callback in subscribers:
            try:
                await callback(event)
            except Exception as e:
                print(f"Error dispatching {event_kind} to subscriber: {e}")

    @property
    def queue_size(self) -> int:
        """Number of pending events in the queue."""
        return self.queue.qsize()

    @property
    def subscriber_count(self) -> int:
        """Total number of subscribers."""
        return sum(len(subs) for subs in self._subscribers.values())
