"""Tests for Milestone 4 (System Info) and Milestone 5 (Windows Controls).

All Windows control operations (shutdown, restart, sleep, lock, volume, screenshot)
are strictly mocked or isolated so the user's workstation is NEVER disrupted.
"""

from collections import namedtuple
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
import psutil

from actions.system_actions import (
    get_battery_status,
    get_cpu_usage,
    get_disk_usage,
    get_memory_usage,
    get_network_status,
    get_os_info,
    get_running_processes,
    get_system_info,
    lock_pc,
    mute,
    restart_pc,
    shutdown_pc,
    sleep_pc,
    take_screenshot,
    toggle_mute,
    unmute,
    volume_down,
    volume_up,
)


class TestSystemActions(unittest.TestCase):
    """Unit test suite for System Information diagnostics (Milestone 4)."""

    # ---------------------------------------------------------
    # get_cpu_usage tests
    # ---------------------------------------------------------
    @patch("actions.system_actions.psutil.cpu_freq")
    @patch("actions.system_actions.psutil.cpu_count")
    @patch("actions.system_actions.psutil.cpu_percent")
    def test_get_cpu_usage_mocked(self, mock_percent, mock_count, mock_freq):
        """CPU usage returns structured core counts, percent, and frequency."""
        mock_percent.return_value = 25.5
        mock_count.side_effect = lambda logical: 16 if logical else 8
        FreqTuple = namedtuple("Freq", ["current", "min", "max"])
        mock_freq.return_value = FreqTuple(current=3200.0, min=800.0, max=4500.0)

        res = get_cpu_usage(interval=0.0)
        self.assertTrue(res.success)
        self.assertEqual(res.data["percent"], 25.5)
        self.assertEqual(res.data["cores_logical"], 16)
        self.assertEqual(res.data["cores_physical"], 8)
        self.assertEqual(res.data["frequency_mhz"]["current"], 3200.0)

    def test_get_cpu_usage_live(self):
        """Live smoke test for get_cpu_usage on current machine."""
        res = get_cpu_usage(interval=0.01)
        self.assertTrue(res.success)
        self.assertIn("percent", res.data)
        self.assertIn("cores_logical", res.data)

    # ---------------------------------------------------------
    # get_memory_usage tests
    # ---------------------------------------------------------
    @patch("actions.system_actions.psutil.virtual_memory")
    def test_get_memory_usage_mocked(self, mock_vm):
        """Memory usage returns formatted bytes and gigabyte metrics."""
        MemTuple = namedtuple("VirtualMemory", ["total", "available", "used", "percent"])
        mock_vm.return_value = MemTuple(
            total=17179869184,  # 16 GB
            available=8589934592,  # 8 GB
            used=8589934592,  # 8 GB
            percent=50.0,
        )

        res = get_memory_usage()
        self.assertTrue(res.success)
        self.assertEqual(res.data["total_gb"], 16.0)
        self.assertEqual(res.data["percent"], 50.0)
        self.assertEqual(res.data["used_gb"], 8.0)

    def test_get_memory_usage_live(self):
        """Live smoke test for get_memory_usage."""
        res = get_memory_usage()
        self.assertTrue(res.success)
        self.assertGreater(res.data["total_bytes"], 0)
        self.assertGreaterEqual(res.data["percent"], 0.0)

    # ---------------------------------------------------------
    # get_disk_usage tests
    # ---------------------------------------------------------
    @patch("actions.system_actions.psutil.disk_usage")
    def test_get_disk_usage_mocked(self, mock_du):
        """Disk usage returns space metrics and usage percentage."""
        DiskTuple = namedtuple("DiskUsage", ["total", "used", "free", "percent"])
        mock_du.return_value = DiskTuple(
            total=536870912000,  # 500 GB
            used=268435456000,  # 250 GB
            free=268435456000,  # 250 GB
            percent=50.0,
        )

        res = get_disk_usage(path="C:\\")
        self.assertTrue(res.success)
        self.assertEqual(res.data["total_gb"], 500.0)
        self.assertEqual(res.data["percent"], 50.0)

    def test_get_disk_usage_live(self):
        """Live smoke test for get_disk_usage."""
        res = get_disk_usage()
        self.assertTrue(res.success)
        self.assertGreater(res.data["total_bytes"], 0)

    # ---------------------------------------------------------
    # get_battery_status tests
    # ---------------------------------------------------------
    @patch("actions.system_actions.psutil.sensors_battery")
    def test_get_battery_status_present(self, mock_battery):
        """Battery status when battery is present."""
        BatteryTuple = namedtuple("Battery", ["percent", "secsleft", "power_plugged"])
        mock_battery.return_value = BatteryTuple(percent=88.5, secsleft=7200, power_plugged=False)

        res = get_battery_status()
        self.assertTrue(res.success)
        self.assertTrue(res.data["has_battery"])
        self.assertEqual(res.data["percent"], 88.5)
        self.assertFalse(res.data["power_plugged"])
        self.assertEqual(res.data["seconds_left"], 7200)

    @patch("actions.system_actions.psutil.sensors_battery")
    def test_get_battery_status_none(self, mock_battery):
        """Battery status when no battery is installed (Desktop PC)."""
        mock_battery.return_value = None

        res = get_battery_status()
        self.assertTrue(res.success)
        self.assertFalse(res.data["has_battery"])
        self.assertIsNone(res.data["percent"])
        self.assertIsNone(res.data["power_plugged"])

    # ---------------------------------------------------------
    # get_network_status tests
    # ---------------------------------------------------------
    @patch("actions.system_actions.psutil.net_io_counters")
    @patch("actions.system_actions.psutil.net_if_addrs")
    @patch("actions.system_actions.psutil.net_if_stats")
    @patch("actions.system_actions.socket.gethostname")
    def test_get_network_status_mocked(self, mock_host, mock_stats, mock_addrs, mock_io):
        """Network status returns structured interface information."""
        mock_host.return_value = "Astra-PC"
        StatTuple = namedtuple("IfStat", ["isup", "duplex", "speed", "mtu"])
        mock_stats.return_value = {"Ethernet": StatTuple(isup=True, duplex=2, speed=1000, mtu=1500)}

        AddrTuple = namedtuple("IfAddr", ["family", "address", "netmask", "broadcast", "ptp"])
        import socket
        mock_addrs.return_value = {
            "Ethernet": [AddrTuple(family=socket.AF_INET, address="192.168.1.100", netmask=None, broadcast=None, ptp=None)]
        }
        mock_io.return_value = namedtuple("NetIo", ["bytes_sent", "bytes_recv"])(1024, 2048)

        res = get_network_status()
        self.assertTrue(res.success)
        self.assertEqual(res.data["hostname"], "Astra-PC")
        self.assertEqual(len(res.data["interfaces"]), 1)
        self.assertEqual(res.data["interfaces"][0]["name"], "Ethernet")
        self.assertEqual(res.data["interfaces"][0]["ipv4_addresses"], ["192.168.1.100"])

    def test_get_network_status_live(self):
        """Live smoke test for network status."""
        res = get_network_status()
        self.assertTrue(res.success)
        self.assertIn("hostname", res.data)
        self.assertIn("interfaces", res.data)

    # ---------------------------------------------------------
    # get_os_info tests
    # ---------------------------------------------------------
    def test_get_os_info(self):
        """OS info returns platform, release, version, and architecture."""
        res = get_os_info()
        self.assertTrue(res.success)
        data = res.data
        self.assertIn("system", data)
        self.assertIn("release", data)
        self.assertIn("version", data)
        self.assertIn("architecture", data)
        self.assertIn("python_version", data)

    # ---------------------------------------------------------
    # get_running_processes tests
    # ---------------------------------------------------------
    @patch("actions.system_actions.psutil.process_iter")
    def test_get_running_processes_handles_errors(self, mock_iter):
        """get_running_processes handles terminating and inaccessible processes gracefully."""
        p_ok = MagicMock()
        p_ok.info = {"pid": 100, "name": "app.exe", "status": "running", "memory_percent": 4.5}

        p_nosuch = MagicMock()
        type(p_nosuch).info = unittest.mock.PropertyMock(side_effect=psutil.NoSuchProcess(101))

        p_denied = MagicMock()
        type(p_denied).info = unittest.mock.PropertyMock(side_effect=psutil.AccessDenied(102))

        mock_iter.return_value = [p_ok, p_nosuch, p_denied]

        res = get_running_processes(limit=10)
        self.assertTrue(res.success)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["processes"][0]["pid"], 100)

    def test_get_running_processes_live(self):
        """Live smoke test for get_running_processes."""
        res = get_running_processes(limit=5)
        self.assertTrue(res.success)
        self.assertLessEqual(len(res.data["processes"]), 5)

    # ---------------------------------------------------------
    # get_system_info tests
    # ---------------------------------------------------------
    def test_get_system_info_aggregated(self):
        """get_system_info combines all subsystem diagnostics into one payload."""
        res = get_system_info()
        self.assertTrue(res.success)
        data = res.data
        self.assertIn("os", data)
        self.assertIn("cpu", data)
        self.assertIn("memory", data)
        self.assertIn("disk", data)
        self.assertIn("battery", data)
        self.assertIn("network", data)

    # ---------------------------------------------------------
    # graceful error handling tests
    # ---------------------------------------------------------
    @patch("actions.system_actions.psutil.virtual_memory")
    def test_memory_usage_exception_handled(self, mock_vm):
        """Unexpected internal exceptions are trapped and returned as failure."""
        mock_vm.side_effect = RuntimeError("Driver failure")
        res = get_memory_usage()
        self.assertFalse(res.success)
        self.assertIn("Driver failure", res.error)


class TestWindowsControls(unittest.TestCase):
    """Unit test suite for Basic Windows Controls (Milestone 5)."""

    # ---------------------------------------------------------
    # Volume Controls (MOCKED)
    # ---------------------------------------------------------
    @patch("actions.system_actions._send_volume_key")
    def test_volume_up(self, mock_send):
        """volume_up emits key events and returns success."""
        res = volume_up(steps=2)
        self.assertTrue(res.success)
        self.assertEqual(res.data["action"], "volume_up")
        self.assertEqual(res.data["steps"], 2)
        mock_send.assert_called_once_with(0xAF, count=2)

    @patch("actions.system_actions._send_volume_key")
    def test_volume_down(self, mock_send):
        """volume_down emits key events and returns success."""
        res = volume_down(steps=3)
        self.assertTrue(res.success)
        self.assertEqual(res.data["action"], "volume_down")
        self.assertEqual(res.data["steps"], 3)
        mock_send.assert_called_once_with(0xAE, count=3)

    @patch("actions.system_actions._send_volume_key")
    def test_mute(self, mock_send):
        """mute triggers mute key event."""
        res = mute()
        self.assertTrue(res.success)
        self.assertEqual(res.data["action"], "mute")
        mock_send.assert_called_once_with(0xAD, count=1)

    @patch("actions.system_actions._send_volume_key")
    def test_unmute(self, mock_send):
        """unmute triggers key events to cancel mute."""
        res = unmute()
        self.assertTrue(res.success)
        self.assertEqual(res.data["action"], "unmute")
        self.assertEqual(mock_send.call_count, 2)

    @patch("actions.system_actions._send_volume_key")
    def test_toggle_mute(self, mock_send):
        """toggle_mute triggers mute toggle event."""
        res = toggle_mute()
        self.assertTrue(res.success)
        self.assertEqual(res.data["action"], "toggle_mute")
        mock_send.assert_called_once_with(0xAD, count=1)

    # ---------------------------------------------------------
    # Screenshot (Isolated Sandbox)
    # ---------------------------------------------------------
    @patch("actions.system_actions.ImageGrab.grab")
    def test_take_screenshot_success(self, mock_grab):
        """take_screenshot saves image to destination without collision."""
        mock_img = Image.new("RGB", (200, 100), color="blue")
        mock_grab.return_value = mock_img

        with tempfile.TemporaryDirectory() as tmp_dir:
            res = take_screenshot(save_dir=tmp_dir, filename="my_capture.png")
            self.assertTrue(res.success)
            saved_path = Path(res.data["path"])
            self.assertTrue(saved_path.exists())
            self.assertEqual(res.data["filename"], "my_capture.png")
            self.assertEqual(res.data["width"], 200)
            self.assertEqual(res.data["height"], 100)

            # Test collision avoidance: second screenshot with same name generates _1.png
            res2 = take_screenshot(save_dir=tmp_dir, filename="my_capture.png")
            self.assertTrue(res2.success)
            self.assertEqual(res2.data["filename"], "my_capture_1.png")
            self.assertTrue(Path(res2.data["path"]).exists())

    @patch("actions.system_actions.ImageGrab.grab")
    def test_take_screenshot_error(self, mock_grab):
        """take_screenshot handles capture failures gracefully."""
        mock_grab.side_effect = OSError("Display buffer unavailable")
        res = take_screenshot()
        self.assertFalse(res.success)
        self.assertEqual(res.error, "Display buffer unavailable")

    # ---------------------------------------------------------
    # Lock PC (MOCKED)
    # ---------------------------------------------------------
    @patch("ctypes.windll.user32.LockWorkStation")
    def test_lock_pc_success(self, mock_lock):
        """lock_pc calls Windows LockWorkStation."""
        mock_lock.return_value = 1
        res = lock_pc()
        self.assertTrue(res.success)
        self.assertTrue(res.data["locked"])
        mock_lock.assert_called_once()

    @patch("ctypes.windll.user32.LockWorkStation")
    def test_lock_pc_failure(self, mock_lock):
        """lock_pc handles Windows LockWorkStation failure."""
        mock_lock.return_value = 0
        res = lock_pc()
        self.assertFalse(res.success)
        self.assertEqual(res.error, "LockFailed")

    # ---------------------------------------------------------
    # Sleep PC (CONFIRMATION GUARD + MOCKED)
    # ---------------------------------------------------------
    def test_sleep_pc_unconfirmed(self):
        """sleep_pc requires confirmation and aborts when confirmed=False."""
        res = sleep_pc(confirmed=False)
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ConfirmationRequired")
        self.assertTrue(res.data["requires_confirmation"])

    @patch("ctypes.windll.powrprof.SetSuspendState")
    def test_sleep_pc_confirmed(self, mock_sleep):
        """sleep_pc executes SetSuspendState when confirmed=True."""
        mock_sleep.return_value = 1
        res = sleep_pc(confirmed=True)
        self.assertTrue(res.success)
        self.assertTrue(res.data["confirmed"])
        mock_sleep.assert_called_once_with(0, 1, 0)

    # ---------------------------------------------------------
    # Restart PC (CONFIRMATION GUARD + MOCKED)
    # ---------------------------------------------------------
    def test_restart_pc_unconfirmed(self):
        """restart_pc requires confirmation and aborts when confirmed=False."""
        res = restart_pc(confirmed=False)
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ConfirmationRequired")
        self.assertTrue(res.data["requires_confirmation"])

    @patch("actions.system_actions.subprocess.run")
    def test_restart_pc_confirmed(self, mock_run):
        """restart_pc executes Windows shutdown /r when confirmed=True."""
        res = restart_pc(confirmed=True)
        self.assertTrue(res.success)
        self.assertTrue(res.data["confirmed"])
        mock_run.assert_called_once_with(["shutdown", "/r", "/t", "0"], check=True)

    # ---------------------------------------------------------
    # Shutdown PC (CONFIRMATION GUARD + MOCKED)
    # ---------------------------------------------------------
    def test_shutdown_pc_unconfirmed(self):
        """shutdown_pc requires confirmation and aborts when confirmed=False."""
        res = shutdown_pc(confirmed=False)
        self.assertFalse(res.success)
        self.assertEqual(res.error, "ConfirmationRequired")
        self.assertTrue(res.data["requires_confirmation"])

    @patch("actions.system_actions.subprocess.run")
    def test_shutdown_pc_confirmed(self, mock_run):
        """shutdown_pc executes Windows shutdown /s when confirmed=True."""
        res = shutdown_pc(confirmed=True)
        self.assertTrue(res.success)
        self.assertTrue(res.data["confirmed"])
        mock_run.assert_called_once_with(["shutdown", "/s", "/t", "0"], check=True)


if __name__ == "__main__":
    unittest.main()
