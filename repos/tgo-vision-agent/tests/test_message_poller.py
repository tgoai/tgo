"""Tests for MessagePoller worker."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.workers.message_poller import MessagePoller


class TestMessagePoller:
    """Tests for MessagePoller class."""

    def test_init(self, mock_agentbay_controller, mock_vlm_client, sample_platform_id):
        """Test MessagePoller initialization."""
        poller = MessagePoller(
            platform_id=sample_platform_id,
            app_type="wechat",
            session_id="test-session",
            controller=mock_agentbay_controller,
            vlm_client=mock_vlm_client,
            poll_interval=5,
        )

        assert poller.platform_id == sample_platform_id
        assert poller.app_type == "wechat"
        assert poller.session_id == "test-session"
        assert poller.poll_interval == 5
        assert poller._running is False

    def test_generate_fingerprint(
        self, mock_agentbay_controller, mock_vlm_client, sample_platform_id
    ):
        """Test message fingerprint generation."""
        poller = MessagePoller(
            platform_id=sample_platform_id,
            app_type="wechat",
            session_id="test-session",
            controller=mock_agentbay_controller,
            vlm_client=mock_vlm_client,
        )

        fp1 = poller._generate_fingerprint("contact1", "hello")
        fp2 = poller._generate_fingerprint("contact1", "hello")
        fp3 = poller._generate_fingerprint("contact2", "hello")

        # Same inputs should produce same fingerprint
        assert fp1 == fp2
        # Different contact should produce different fingerprint
        assert fp1 != fp3

    def test_is_message_processed(
        self, mock_agentbay_controller, mock_vlm_client, sample_platform_id
    ):
        """Test message processing tracking."""
        poller = MessagePoller(
            platform_id=sample_platform_id,
            app_type="wechat",
            session_id="test-session",
            controller=mock_agentbay_controller,
            vlm_client=mock_vlm_client,
        )

        fingerprint = "test-fingerprint"
        assert poller._is_message_processed(fingerprint) is False

        poller._mark_message_processed(fingerprint)
        assert poller._is_message_processed(fingerprint) is True

    def test_mark_message_processed_bounds_set_size(
        self, mock_agentbay_controller, mock_vlm_client, sample_platform_id
    ):
        """Test that fingerprint set is bounded."""
        poller = MessagePoller(
            platform_id=sample_platform_id,
            app_type="wechat",
            session_id="test-session",
            controller=mock_agentbay_controller,
            vlm_client=mock_vlm_client,
        )

        # Add more than 10000 fingerprints
        for i in range(10005):
            poller._mark_message_processed(f"fp-{i}")

        # Set should be bounded
        assert len(poller._processed_fingerprints) <= 10000

    @pytest.mark.asyncio
    async def test_start_stop(
        self, mock_agentbay_controller, mock_vlm_client, sample_platform_id
    ):
        """Test start and stop methods."""
        poller = MessagePoller(
            platform_id=sample_platform_id,
            app_type="wechat",
            session_id="test-session",
            controller=mock_agentbay_controller,
            vlm_client=mock_vlm_client,
            poll_interval=1,
        )

        # Mock the automator factory
        with patch("app.workers.message_poller.AppAutomatorFactory") as mock_factory:
            mock_automator = AsyncMock()
            mock_automator.get_login_status = AsyncMock(
                return_value=MagicMock(login_status=MagicMock(value="offline"))
            )
            mock_factory.create.return_value = mock_automator

            await poller.start()
            assert poller._running is True

            await poller.stop()
            assert poller._running is False

    @pytest.mark.asyncio
    async def test_start_twice_does_nothing(
        self, mock_agentbay_controller, mock_vlm_client, sample_platform_id
    ):
        """Test that starting twice doesn't create duplicate tasks."""
        poller = MessagePoller(
            platform_id=sample_platform_id,
            app_type="wechat",
            session_id="test-session",
            controller=mock_agentbay_controller,
            vlm_client=mock_vlm_client,
            poll_interval=60,  # Long interval to prevent actual polling
        )

        with patch("app.workers.message_poller.AppAutomatorFactory"):
            await poller.start()
            first_task = poller._task

            await poller.start()  # Should log warning and return
            second_task = poller._task

            assert first_task is second_task

            await poller.stop()
