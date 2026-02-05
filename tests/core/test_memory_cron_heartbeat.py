"""Tests for memory, cron, and heartbeat features."""

import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from agenix.memory import MemoryStore
from agenix.cron import CronService, CronSchedule
from agenix.heartbeat import HeartbeatService


class TestMemory:
    """Tests for MemoryStore."""

    def test_memory_store_init(self, tmp_path):
        """Test memory store initialization."""
        memory = MemoryStore(tmp_path)
        assert memory.workspace == tmp_path
        assert memory.memory_dir.exists()
        assert memory.memory_file == memory.memory_dir / "MEMORY.md"

    def test_append_today(self, tmp_path):
        """Test appending to today's notes."""
        memory = MemoryStore(tmp_path)
        memory.append_today("First note")
        memory.append_today("Second note")

        content = memory.read_today()
        assert "First note" in content
        assert "Second note" in content
        assert datetime.now().strftime("%Y-%m-%d") in content

    def test_long_term_memory(self, tmp_path):
        """Test long-term memory read/write."""
        memory = MemoryStore(tmp_path)
        content = "# Long-term knowledge\n\n- Fact 1\n- Fact 2"
        memory.write_long_term(content)

        read_content = memory.read_long_term()
        assert read_content == content

    def test_get_memory_context(self, tmp_path):
        """Test getting full memory context."""
        memory = MemoryStore(tmp_path)
        memory.append_today("Today's note")
        memory.write_long_term("Long-term fact")

        context = memory.get_memory_context()
        assert "Today's note" in context
        assert "Long-term fact" in context


class TestCron:
    """Tests for CronService."""

    @pytest.mark.asyncio
    async def test_cron_service_init(self, tmp_path):
        """Test cron service initialization."""
        store_path = tmp_path / "cron.json"
        cron = CronService(store_path)

        await cron.start()
        assert cron._running
        assert store_path.exists()
        cron.stop()

    @pytest.mark.asyncio
    async def test_add_job(self, tmp_path):
        """Test adding a cron job."""
        store_path = tmp_path / "cron.json"
        cron = CronService(store_path)
        await cron.start()

        job = cron.add_job(
            name="Test job",
            schedule=CronSchedule(kind="every", every_ms=60000),
            message="Test message"
        )

        assert job.name == "Test job"
        assert job.enabled
        assert job.schedule.kind == "every"
        assert job.schedule.every_ms == 60000

        jobs = cron.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == job.id

        cron.stop()

    @pytest.mark.asyncio
    async def test_remove_job(self, tmp_path):
        """Test removing a cron job."""
        store_path = tmp_path / "cron.json"
        cron = CronService(store_path)
        await cron.start()

        job = cron.add_job(
            name="Test job",
            schedule=CronSchedule(kind="every", every_ms=60000),
            message="Test message"
        )

        removed = cron.remove_job(job.id)
        assert removed

        jobs = cron.list_jobs()
        assert len(jobs) == 0

        cron.stop()

    @pytest.mark.asyncio
    async def test_job_execution(self, tmp_path):
        """Test job execution."""
        store_path = tmp_path / "cron.json"
        executed = []

        async def on_job(job):
            executed.append(job.id)
            return "OK"

        cron = CronService(store_path, on_job=on_job)
        await cron.start()

        job = cron.add_job(
            name="Test job",
            schedule=CronSchedule(kind="every", every_ms=100),
            message="Test message"
        )

        # Wait for job to execute
        await asyncio.sleep(0.2)

        assert job.id in executed

        cron.stop()


class TestHeartbeat:
    """Tests for HeartbeatService."""

    @pytest.mark.asyncio
    async def test_heartbeat_init(self, tmp_path):
        """Test heartbeat service initialization."""
        heartbeat = HeartbeatService(
            workspace=tmp_path,
            interval_s=1,
            enabled=True
        )

        assert heartbeat.workspace == tmp_path
        assert heartbeat.interval_s == 1
        assert heartbeat.enabled

    @pytest.mark.asyncio
    async def test_heartbeat_skip_empty(self, tmp_path):
        """Test heartbeat skips empty file."""
        executed = []

        async def on_heartbeat(prompt):
            executed.append(prompt)
            return "OK"

        heartbeat = HeartbeatService(
            workspace=tmp_path,
            on_heartbeat=on_heartbeat,
            interval_s=0.1,
            enabled=True
        )

        # Create empty HEARTBEAT.md
        (tmp_path / "HEARTBEAT.md").write_text("# Title\n\n")

        await heartbeat.start()
        await asyncio.sleep(0.2)

        # Should not execute because file is empty
        assert len(executed) == 0

        heartbeat.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_execution(self, tmp_path):
        """Test heartbeat execution."""
        executed = []

        async def on_heartbeat(prompt):
            executed.append(prompt)
            return "OK"

        heartbeat = HeartbeatService(
            workspace=tmp_path,
            on_heartbeat=on_heartbeat,
            interval_s=0.1,
            enabled=True
        )

        # Create HEARTBEAT.md with content
        (tmp_path / "HEARTBEAT.md").write_text("# Tasks\n\n- [ ] Do something")

        await heartbeat.start()
        await asyncio.sleep(0.2)

        # Should execute because file has content
        assert len(executed) > 0

        heartbeat.stop()

    @pytest.mark.asyncio
    async def test_manual_trigger(self, tmp_path):
        """Test manual heartbeat trigger."""
        async def on_heartbeat(prompt):
            return "Triggered"

        heartbeat = HeartbeatService(
            workspace=tmp_path,
            on_heartbeat=on_heartbeat,
            enabled=False
        )

        response = await heartbeat.trigger_now()
        assert response == "Triggered"


@pytest.fixture
def tmp_path():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
