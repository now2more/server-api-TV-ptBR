import configparser
import difflib
import ipaddress
import math
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import urlsplit

import pytz

from utils.performance import PERFORMANCE_MODES, get_performance_settings
from utils.process import no_window_process_kwargs
from utils.resources import resource_path


@dataclass(frozen=True)
class ConfigRule:
    kind: str = "string"
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    allow_empty: bool = False


@dataclass(frozen=True)
class ConfigIssue:
    source: str
    section: str | None
    key: str | None
    value: str | None
    message: str

    def __str__(self):
        location = self.source
        if self.section:
            location += f": [{self.section}]"
        if self.key:
            location += f" {self.key}"
        if self.value is not None:
            display_value = self.value if len(self.value) <= 80 else f"{self.value[:77]}..."
            location += f" = {display_value!r}"
        return f"{location}：{self.message}"


class ConfigValidationError(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        details = "\n".join(f"- {issue}" for issue in self.issues)
        super().__init__(f"配置校验失败：\n{details}")


BOOLEAN_KEYS = {
    "ipv6_support",
    "open_auto_disable_source",
    "open_empty_category",
    "open_epg",
    "open_filter_ad",
    "open_filter_resolution",
    "open_filter_speed",
    "open_full_speed_test",
    "open_headers",
    "open_history",
    "open_local",
    "open_m3u_result",
    "open_request",
    "open_realtime_write",
    "open_rtmp",
    "open_service",
    "open_speed_test",
    "open_stream_screenshot",
    "open_subscribe",
    "open_subscribe_epg",
    "open_subscribe_logo",
    "open_supply",
    "open_unmatch_category",
    "open_update",
    "open_update_time",
    "open_url_info",
    "open_use_cache",
    "speed_test_filter_host",
    "update_startup",
}

CONFIG_SCHEMA = {
    **{key: ConfigRule(kind="boolean") for key in BOOLEAN_KEYS},
    # [PT-BR] ``urls_limit`` is retained as a backwards-compatible alias.  New
    # [PT-BR] configurations should use the output and speed-test settings below.
    "urls_limit": ConfigRule(kind="integer", minimum=1),
    "output_urls_limit": ConfigRule(kind="integer", minimum=1),
    "speed_test_target": ConfigRule(kind="integer", minimum=0),
    "quick_test_target": ConfigRule(kind="integer", minimum=0),
    "speed_test_mode": ConfigRule(kind="enum", choices=("quick", "full", "manual")),
    "app_port": ConfigRule(kind="integer", minimum=1, maximum=65535),
    "service_port": ConfigRule(kind="integer", minimum=1, maximum=65535),
    "nginx_http_port": ConfigRule(kind="integer", minimum=1, maximum=65535),
    "nginx_rtmp_port": ConfigRule(kind="integer", minimum=1, maximum=65535),
    "local_num": ConfigRule(kind="integer", minimum=0),
    "subscribe_num": ConfigRule(kind="integer", minimum=0),
    "speed_test_limit": ConfigRule(kind="integer", minimum=0),
    "speed_test_timeout": ConfigRule(kind="integer", minimum=1),
    "stream_screenshot_timeout": ConfigRule(kind="integer", minimum=1, maximum=60),
    "stream_screenshot_width": ConfigRule(kind="integer", minimum=160, maximum=3840),
    "request_timeout": ConfigRule(kind="integer", minimum=1),
    "rtmp_idle_timeout": ConfigRule(kind="integer", minimum=0),
    "rtmp_max_streams": ConfigRule(kind="integer", minimum=1),
    "min_speed": ConfigRule(kind="float", minimum=0),
    "update_interval": ConfigRule(kind="float", minimum=0, allow_empty=True),
    "update_time_position": ConfigRule(kind="enum", choices=("top", "bottom")),
    "language": ConfigRule(kind="enum", choices=("zh_CN", "en")),
    "update_mode": ConfigRule(kind="enum", choices=("interval", "time")),
    "public_scheme": ConfigRule(kind="enum", choices=("http", "https")),
    "performance_mode": ConfigRule(kind="enum", choices=tuple(PERFORMANCE_MODES)),
    "ipv_type": ConfigRule(kind="enum", choices=("ipv4", "ipv6", "all")),
    "logo_type": ConfigRule(kind="enum", choices=("png", "jpg", "jpeg")),
    "rtmp_transcode_mode": ConfigRule(kind="enum", choices=("copy", "auto")),
    "ipv_type_prefer": ConfigRule(
        kind="list", choices=("ipv4", "ipv6", "auto")
    ),
    "origin_type_prefer": ConfigRule(
        kind="list", choices=("local", "subscribe"), allow_empty=True
    ),
    "sort_by": ConfigRule(
        kind="list", choices=("speed", "delay", "resolution")
    ),
    "source_file": ConfigRule(),
    "final_file": ConfigRule(),
    "update_times": ConfigRule(kind="times", allow_empty=True),
    "time_zone": ConfigRule(kind="timezone"),
    "public_domain": ConfigRule(),
    "public_url": ConfigRule(kind="public_url", allow_empty=True),
    "cdn_url": ConfigRule(allow_empty=True),
    "http_proxy": ConfigRule(allow_empty=True),
    "user_agent": ConfigRule(allow_empty=True),
    "min_resolution": ConfigRule(kind="resolution"),
    "max_resolution": ConfigRule(kind="resolution"),
    "resolution_speed_map": ConfigRule(kind="resolution_speed_map", allow_empty=True),
    "location": ConfigRule(allow_empty=True),
    "isp": ConfigRule(allow_empty=True),
    "logo_url": ConfigRule(allow_empty=True),
}


def _suggest(value, choices):
    matches = difflib.get_close_matches(
        str(value).lower(),
        [str(choice).lower() for choice in choices],
        n=1,
        cutoff=0.6,
    )
    if not matches:
        return None
    match = matches[0]
    return next(choice for choice in choices if str(choice).lower() == match)


def _choice_message(choices, suggestion=None):
    message = f"可选值为 {', '.join(choices)}"
    if suggestion is not None:
        message += f'；是否想填写 "{suggestion}"？'
    return message


def _is_usable_ipv4(address: str | None) -> bool:
    try:
        ip = ipaddress.ip_address(address or "")
        return ip.version == 4 and not (ip.is_loopback or ip.is_link_local or ip.is_unspecified)
    except ValueError:
        return False


def _get_command_output(args: list[str]) -> str:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
            **no_window_process_kwargs(),
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def _get_primary_ipv4() -> str | None:
    if sys.platform == "win32":
        command = (
            "$routes = Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
            "Sort-Object RouteMetric, InterfaceMetric; "
            "$route = @($routes | Where-Object { $_.InterfaceAlias -notmatch "
            "'Loopback|vEthernet|WSL|Docker|VMware|VirtualBox|TAP|TUN' })[0]; "
            "if (-not $route) { $route = @($routes)[0] }; "
            "if ($route) { Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex "
            "-AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' } | "
            "Select-Object -First 1 -ExpandProperty IPAddress }"
        )
        address = _get_command_output(["powershell", "-NoProfile", "-Command", command])
        return address if _is_usable_ipv4(address) else None
    if sys.platform == "darwin":
        route = _get_command_output(["route", "-n", "get", "default"])
        interface = next(
            (
                line.split(":", 1)[1].strip()
                for line in route.splitlines()
                if line.strip().startswith("interface:")
            ),
            None,
        )
        address = _get_command_output(["ipconfig", "getifaddr", interface]) if interface else ""
        return address if _is_usable_ipv4(address) else None
    if sys.platform.startswith("linux"):
        route = _get_command_output(["ip", "route", "get", "1.1.1.1"])
        match = re.search(r"\bsrc\s+(\S+)", route)
        address = match.group(1) if match else ""
        return address if _is_usable_ipv4(address) else None
    return None


def get_resolution_value(resolution_str):
"""
[PT-BR]     Get resolution value from string
"""
    pattern = r"(\d+)[xX*](\d+)"
    match = re.search(pattern, resolution_str)
    if match:
        width, height = map(int, match.groups())
        return width * height
    else:
        return 0


class ConfigManager:

    def __init__(
        self,
        default_config_path=None,
        user_config_path=None,
        environ=None,
    ):
        self.config = None
        self._default_config_path = default_config_path
        self._user_config_path = user_config_path
        self._environ = os.environ if environ is None else environ
        self._sources = {}
        self._detected_public_domain = None
        self.load()
        self.override_config_with_env()
        self.validate()

    def __getattr__(self, name, *args, **kwargs):
        return getattr(self.config, name, *args, **kwargs)

    @property
    def open_service(self):
        return self.config.getboolean("Settings", "open_service", fallback=True)

    @property
    def open_update(self):
        return self.config.getboolean("Settings", "open_update", fallback=True)

    @property
    def open_use_cache(self):
        return self.config.getboolean("Settings", "open_use_cache", fallback=True)

    @property
    def open_request(self):
        return self.config.getboolean("Settings", "open_request", fallback=False)

    @property
    def open_filter_speed(self):
        return self.config.getboolean(
            "Settings", "open_filter_speed", fallback=True
        )

    @property
    def open_filter_resolution(self):
        return self.config.getboolean(
            "Settings", "open_filter_resolution", fallback=True
        )

    @property
    def open_filter_ad(self):
        return self.config.getboolean(
            "Settings", "open_filter_ad", fallback=True
        )

    @property
    def ipv_type(self):
        return self.config.get("Settings", "ipv_type", fallback="all").lower()

    @property
    def open_ipv6(self):
        return (
                "ipv6" in self.ipv_type or "all" in self.ipv_type
        )

    @property
    def ipv_type_prefer(self):
        return [
            ipv_type_value.lower()
            for ipv_type in self.config.get(
                "Settings", "ipv_type_prefer", fallback=""
            ).split(",")
            if (ipv_type_value := ipv_type.strip())
        ]

    @property
    def ipv6_support(self):
        return self.config.getboolean("Settings", "ipv6_support", fallback=False)

    @property
    def origin_type_prefer(self):
        return [
            origin_value.lower()
            for origin in self.config.get(
                "Settings",
                "origin_type_prefer",
                fallback="",
            ).split(",")
            if (origin_value := origin.strip())
        ]

    @property
    def subscribe_num(self):
        return self.config.getint("Settings", "subscribe_num", fallback=10)

    @property
    def source_limits(self):
        return {
            "all": self.output_urls_limit,
            "local": self.local_num,
            "subscribe": self.subscribe_num,
        }

    @property
    def min_speed(self):
        return self.config.getfloat("Settings", "min_speed", fallback=0.5)

    @property
    def min_resolution(self):
        return self.config.get("Settings", "min_resolution", fallback="1920x1080")

    @property
    def min_resolution_value(self):
        return get_resolution_value(self.min_resolution)

    @property
    def max_resolution(self):
        return self.config.get("Settings", "max_resolution", fallback="1920x1080")

    @property
    def max_resolution_value(self):
        return get_resolution_value(self.max_resolution)

    @property
    def urls_limit(self):
"""
[PT-BR]         return self.output_urls_limit



[PT-BR]     @property

[PT-BR]     def output_urls_limit(self):

[PT-BR]         configured = self.config.get("Settings", "output_urls_limit", fallback="").strip()

[PT-BR]         output_source = self._sources.get(("Settings", "output_urls_limit"))

[PT-BR]         legacy_source = self._sources.get(("Settings", "urls_limit"))

[PT-BR]         # A legacy value from the user file must continue to override the

[PT-BR]         # shipped default output value during migration.

[PT-BR]         if (

[PT-BR]             legacy_source

[PT-BR]             and legacy_source != self._default_config_path

[PT-BR]             and output_source == self._default_config_path

[PT-BR]         ):

[PT-BR]             return self.config.getint("Settings", "urls_limit", fallback=10)

[PT-BR]         if configured:

[PT-BR]             return max(1, int(configured))

[PT-BR]         return self.config.getint("Settings", "urls_limit", fallback=10)



[PT-BR]     @property

[PT-BR]     def speed_test_target(self):
"""

        A value of zero follows the output limit.  ``open_full_speed_test``
        still takes precedence and tests the entire candidate pool.
        """
        # [PT-BR] ``quick_test_target`` is the descriptive name used by the layered
        # [PT-BR] candidate model; retain ``speed_test_target`` for compatibility.
        quick_value = self.config.getint("Settings", "quick_test_target", fallback=0)
        value = quick_value or self.config.getint("Settings", "speed_test_target", fallback=0)
        return self.output_urls_limit if value <= 0 else value

    @property
    def quick_test_target(self):
"""
[PT-BR]         return self.speed_test_target



[PT-BR]     @property

[PT-BR]     def speed_test_mode(self):
"""
        mode = self.config.get("Settings", "speed_test_mode", fallback="").strip().lower()
        mode_source = self._sources.get(("Settings", "speed_test_mode"))
        legacy_source = self._sources.get(("Settings", "open_speed_test"))
        full_source = self._sources.get(("Settings", "open_full_speed_test"))
        if (
            mode_source == self._default_config_path
            and (
                (legacy_source and legacy_source != self._default_config_path)
                or (full_source and full_source != self._default_config_path)
            )
        ):
            if not self.config.getboolean("Settings", "open_speed_test", fallback=True):
                return "manual"
            return "full" if self.config.getboolean("Settings", "open_full_speed_test", fallback=False) else "quick"
        if mode in {"quick", "full", "manual"}:
            return mode
        if not self.config.getboolean("Settings", "open_speed_test", fallback=True):
            return "manual"
        return "full" if self.open_full_speed_test else "quick"

    @property
    def open_url_info(self):
        return self.config.getboolean("Settings", "open_url_info", fallback=True)

    @property
    def source_file(self):
        return self.config.get("Settings", "source_file", fallback="config/demo.txt")

    @property
    def final_file(self):
        return self.config.get("Settings", "final_file", fallback="output/result.txt")

    @property
    def open_m3u_result(self):
        return self.config.getboolean("Settings", "open_m3u_result", fallback=True)

    @property
    def open_subscribe(self):
        return self.config.getboolean("Settings", f"open_subscribe", fallback=True)

    @property
    def open_method(self):
        return {
            "epg": self.open_epg,
            "local": self.open_local,
            "subscribe": self.open_subscribe,
        }

    @property
    def open_history(self):
        return self.config.getboolean("Settings", "open_history", fallback=True)

    @property
    def open_speed_test(self):
        return self.config.getboolean("Settings", "open_speed_test", fallback=True)

    @property
    def open_stream_screenshot(self):
        return self.config.getboolean("Settings", "open_stream_screenshot", fallback=False)

    @property
    def stream_screenshot_timeout(self):
        return self.config.getint("Settings", "stream_screenshot_timeout", fallback=5)

    @property
    def stream_screenshot_width(self):
        return self.config.getint("Settings", "stream_screenshot_width", fallback=640)

    @property
    def open_update_time(self):
        return self.config.getboolean("Settings", "open_update_time", fallback=True)

    @property
    def request_timeout(self):
        return self.config.getint("Settings", "request_timeout", fallback=10)

    @property
    def speed_test_timeout(self):
        return self.config.getint("Settings", "speed_test_timeout", fallback=10)

    @property
    def open_empty_category(self):
        return self.config.getboolean("Settings", "open_empty_category", fallback=True)

    @property
    def app_port(self):
        return self.config.getint("Settings", "app_port", fallback=5180)

    @property
    def service_port(self):
        legacy_port = self.config.getint("Settings", "nginx_http_port", fallback=8080)
        if not self.config.has_option("Settings", "service_port"):
            return legacy_port
        service_source = self._sources.get(("Settings", "service_port"))
        legacy_source = self._sources.get(("Settings", "nginx_http_port"))
        if (
            service_source == self._default_config_path
            and legacy_source
            and legacy_source != self._default_config_path
        ):
            return legacy_port
        return self.config.getint("Settings", "service_port", fallback=legacy_port)

    @property
    def nginx_http_port(self):
"""
[PT-BR]         return self.service_port



[PT-BR]     @property

[PT-BR]     def nginx_rtmp_port(self):

[PT-BR]         return self.config.getint("Settings", "nginx_rtmp_port", fallback=1935)



[PT-BR]     @property

[PT-BR]     def open_supply(self):

[PT-BR]         return self.config.getboolean("Settings", "open_supply", fallback=False)



[PT-BR]     @property

[PT-BR]     def sort_by(self):

[PT-BR]         raw = self.config.get("Settings", "sort_by", fallback="speed")

[PT-BR]         allowed = ("speed", "delay", "resolution")

[PT-BR]         result = [s.strip().lower() for s in str(raw).split(",") if s.strip().lower() in allowed]

[PT-BR]         return result or ["speed"]



[PT-BR]     @property

[PT-BR]     def update_time_position(self):

[PT-BR]         return self.config.get("Settings", "update_time_position", fallback="top")



[PT-BR]     @property

[PT-BR]     def time_zone(self):

[PT-BR]         return self.config.get("Settings", "time_zone", fallback="Asia/Shanghai")



[PT-BR]     @property

[PT-BR]     def open_local(self):

[PT-BR]         return self.config.getboolean("Settings", "open_local", fallback=True)



[PT-BR]     @property

[PT-BR]     def local_num(self):

[PT-BR]         return self.config.getint("Settings", "local_num", fallback=10)



[PT-BR]     @property

[PT-BR]     def speed_test_filter_host(self):

[PT-BR]         return self.config.getboolean("Settings", "speed_test_filter_host", fallback=False)



[PT-BR]     @property

[PT-BR]     def cdn_urls(self):

[PT-BR]         raw = self.config.get("Settings", "cdn_url", fallback="")

[PT-BR]         return [u.strip() for u in re.split(r"[,\n]", raw) if u.strip()]



[PT-BR]     @property

[PT-BR]     def cdn_url(self):

[PT-BR]         urls = self.cdn_urls

[PT-BR]         return urls[0] if urls else ""



[PT-BR]     @property

[PT-BR]     def open_rtmp(self):

[PT-BR]         return not self._environ.get("GITHUB_ACTIONS") and self.config.getboolean("Settings", "open_rtmp", fallback=True)



[PT-BR]     @property

[PT-BR]     def rtmp_available(self):

[PT-BR]         if not self.open_rtmp:

[PT-BR]             return False

[PT-BR]         if sys.platform != "darwin":

[PT-BR]             return True

[PT-BR]         from utils.rtmp_runtime import rtmp_runtime_status

[PT-BR]         return rtmp_runtime_status().get("available", False)



[PT-BR]     @property

[PT-BR]     def open_headers(self):

[PT-BR]         return self.config.getboolean("Settings", "open_headers", fallback=True)



[PT-BR]     @property

[PT-BR]     def user_agent(self):

[PT-BR]         return self.config.get("Settings", "user_agent", fallback="").strip()



[PT-BR]     @property

[PT-BR]     def open_epg(self):

[PT-BR]         return self.config.getboolean("Settings", "open_epg", fallback=True)



[PT-BR]     @property

[PT-BR]     def open_subscribe_epg(self):

[PT-BR]         return self.config.getboolean("Settings", "open_subscribe_epg", fallback=False)



[PT-BR]     @property

[PT-BR]     def speed_test_limit(self):

[PT-BR]         return self.config.getint("Settings", "speed_test_limit", fallback=0)



[PT-BR]     @property

[PT-BR]     def performance_mode(self):

[PT-BR]         mode = self.config.get("Settings", "performance_mode", fallback="auto").lower()

[PT-BR]         return mode if mode in PERFORMANCE_MODES else "auto"



[PT-BR]     @property

[PT-BR]     def performance_settings(self):

[PT-BR]         return get_performance_settings(self.performance_mode, self.speed_test_limit)



[PT-BR]     @property

[PT-BR]     def location(self):

[PT-BR]         return [

[PT-BR]             l.strip()

[PT-BR]             for l in self.config.get(

[PT-BR]                 "Settings", "location", fallback=""

[PT-BR]             ).split(",")

[PT-BR]             if l.strip()

[PT-BR]         ]



[PT-BR]     @property

[PT-BR]     def isp(self):

[PT-BR]         return [

[PT-BR]             i.strip()

[PT-BR]             for i in self.config.get(

[PT-BR]                 "Settings", "isp", fallback=""

[PT-BR]             ).split(",")

[PT-BR]             if i.strip()

[PT-BR]         ]



[PT-BR]     @property

[PT-BR]     def update_mode(self):

[PT-BR]         return self.config.get("Settings", "update_mode", fallback="interval")



[PT-BR]     @property

[PT-BR]     def update_interval(self):

[PT-BR]         raw = self.config.get("Settings", "update_interval", fallback="12")

[PT-BR]         if raw is None or str(raw).strip() == "":

[PT-BR]             return None

[PT-BR]         try:

[PT-BR]             return float(raw)

[PT-BR]         except (ValueError, TypeError):

[PT-BR]             return 12.0



[PT-BR]     @property

[PT-BR]     def update_times(self):

[PT-BR]         return self.config.get("Settings", "update_times", fallback="")



[PT-BR]     @property

[PT-BR]     def update_startup(self):

[PT-BR]         return self.config.getboolean("Settings", "update_startup", fallback=True)



[PT-BR]     @property

[PT-BR]     def logo_url(self):

[PT-BR]         return self.config.get("Settings", "logo_url", fallback="")



[PT-BR]     @property

[PT-BR]     def logo_type(self):

[PT-BR]         return self.config.get("Settings", "logo_type", fallback="png")



[PT-BR]     @property

[PT-BR]     def open_subscribe_logo(self):

[PT-BR]         return self.config.getboolean("Settings", "open_subscribe_logo", fallback=True)



[PT-BR]     @property

[PT-BR]     def rtmp_idle_timeout(self):

[PT-BR]         return self.config.getint("Settings", "rtmp_idle_timeout", fallback=300)



[PT-BR]     @property

[PT-BR]     def rtmp_max_streams(self):

[PT-BR]         return self.config.getint("Settings", "rtmp_max_streams", fallback=10)



[PT-BR]     @property

[PT-BR]     def rtmp_transcode_mode(self):

[PT-BR]         return (self.config.get("Settings", "rtmp_transcode_mode", fallback="copy") or "copy").lower()



[PT-BR]     @property

[PT-BR]     def public_scheme(self):

[PT-BR]         return self.config.get("Settings", "public_scheme", fallback="http") or "http"



[PT-BR]     @property

[PT-BR]     def public_url(self):

[PT-BR]         return self.config.get("Settings", "public_url", fallback="").strip().rstrip("/")



[PT-BR]     @property

[PT-BR]     def public_domain(self):

[PT-BR]         cfg = self.config.get("Settings", "public_domain", fallback="127.0.0.1")

[PT-BR]         if cfg and cfg != "127.0.0.1":

[PT-BR]             return cfg

[PT-BR]         if self._detected_public_domain is None:

[PT-BR]             self._detected_public_domain = _get_primary_ipv4()

[PT-BR]             if not self._detected_public_domain:

[PT-BR]                 try:

[PT-BR]                     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

[PT-BR]                     try:

[PT-BR]                         s.connect(("8.8.8.8", 80))

[PT-BR]                         ip = s.getsockname()[0]

[PT-BR]                     finally:

[PT-BR]                         s.close()

[PT-BR]                     if ip and not ip.startswith("127."):

[PT-BR]                         self._detected_public_domain = ip

[PT-BR]                 except Exception:

[PT-BR]                     pass

[PT-BR]             self._detected_public_domain = self._detected_public_domain or cfg

[PT-BR]         return self._detected_public_domain



[PT-BR]     @property

[PT-BR]     def public_port(self):

[PT-BR]         env = self._environ.get("PUBLIC_PORT")

[PT-BR]         if env:

[PT-BR]             return int(env)

[PT-BR]         return self.service_port if self.rtmp_available else self.app_port



[PT-BR]     def environment_override_name(self, key: str) -> str | None:

[PT-BR]         source_key = key

[PT-BR]         if key == "service_port":

[PT-BR]             service_source = self._sources.get(("Settings", "service_port"))

[PT-BR]             legacy_source = self._sources.get(("Settings", "nginx_http_port"))

[PT-BR]             if (

[PT-BR]                 service_source == self._default_config_path

[PT-BR]                 and legacy_source

[PT-BR]                 and legacy_source != self._default_config_path

[PT-BR]             ):

[PT-BR]                 source_key = "nginx_http_port"

[PT-BR]         source = self._sources.get(("Settings", source_key), "")

[PT-BR]         prefix = "环境变量 "

[PT-BR]         return source[len(prefix):] if source.startswith(prefix) else None



[PT-BR]     @property

[PT-BR]     def language(self):

[PT-BR]         return self.config.get("Settings", "language", fallback="zh_CN")



[PT-BR]     @property

[PT-BR]     def http_proxy(self):

[PT-BR]         return self.config.get("Settings", "http_proxy", fallback="").strip()



[PT-BR]     @property

[PT-BR]     def open_realtime_write(self):

[PT-BR]         return self.config.getboolean("Settings", "open_realtime_write", fallback=True)



[PT-BR]     @property

[PT-BR]     def open_full_speed_test(self):

[PT-BR]         return self.config.getboolean("Settings", "open_full_speed_test", fallback=False)



[PT-BR]     @property

[PT-BR]     def resolution_speed_map(self):

[PT-BR]         mapping = {}

[PT-BR]         for item in self.config.get("Settings", "resolution_speed_map", fallback="").split(","):

[PT-BR]             if ":" in item:

[PT-BR]                 resolution_part, speed_part = item.split(":", 1)

[PT-BR]                 resolution = resolution_part.strip()

[PT-BR]                 try:

[PT-BR]                     speed = float(speed_part.strip())

[PT-BR]                     mapping[resolution] = speed

[PT-BR]                 except ValueError:

[PT-BR]                     pass

[PT-BR]         return mapping



[PT-BR]     @property

[PT-BR]     def open_unmatch_category(self):

[PT-BR]         return self.config.getboolean("Settings", "open_unmatch_category", fallback=False)



[PT-BR]     @property

[PT-BR]     def open_auto_disable_source(self):

[PT-BR]         return self.config.getboolean("Settings", "open_auto_disable_source", fallback=False)



[PT-BR]     def load(self):
"""
        Load the config
        """
        self._detected_public_domain = None
        self.config = configparser.ConfigParser(interpolation=None)
        if self._user_config_path is None:
            self._user_config_path = resource_path(
                "config/user_config.ini", persistent=True
            )
        if self._default_config_path is None:
            self._default_config_path = (
                os.path.join(sys._MEIPASS, "config/config.ini")
                if getattr(sys, "frozen", False)
                else resource_path("config/config.ini")
            )

        # [PT-BR] user config overwrites default config
        config_files = [self._default_config_path, self._user_config_path]
        for config_file in config_files:
            if os.path.exists(config_file):
                incoming = configparser.ConfigParser(interpolation=None)
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        incoming.read_file(f, source=config_file)
                except (OSError, configparser.Error) as exc:
                    raise ConfigValidationError([
                        ConfigIssue(
                            config_file,
                            None,
                            None,
                            None,
                            f"无法读取配置：{exc}",
                        )
                    ]) from exc
                for section in incoming.sections():
                    if not self.config.has_section(section):
                        self.config.add_section(section)
                    for key, value in incoming.items(section, raw=True):
                        self.config.set(section, key, value)
                        self._sources[(section, key)] = config_file

    def override_config_with_env(self):
        for section in self.config.sections():
            for key in self.config[section]:
                section_key = f"{section}_{key}"
                candidates = (key, key.upper(), section_key, section_key.upper())
                for env_name in candidates:
                    env_val = self._environ.get(env_name)
                    if env_val is not None:
                        # [PT-BR] Empty Compose placeholders must not clear values saved
                        # [PT-BR] in the mounted configuration.
                        if (
                            key in {"public_url", "http_proxy"}
                            and not str(env_val).strip()
                        ):
                            continue
                        self.config.set(section, key, env_val)
                        self._sources[(section, key)] = f"环境变量 {env_name}"
                        break

    def _source(self, section, key):
        return self._sources.get((section, key), "配置")

    def _issue(self, section, key, value, message):
        return ConfigIssue(
            self._source(section, key),
            section,
            key,
            value,
            message,
        )

    def _validate_value(self, section, key, value, rule):
        value = str(value).strip()
        if not value:
            if rule.allow_empty:
                return []
            return [self._issue(section, key, value, "值不能为空")]

        if rule.kind == "boolean":
            choices = ("True", "False")
            normalized = value.lower()
            if normalized not in {"true", "false"}:
                return [
                    self._issue(
                        section,
                        key,
                        value,
                        _choice_message(choices, _suggest(value, choices)),
                    )
                ]
            return []

        if rule.kind in {"integer", "float"}:
            try:
                number = int(value) if rule.kind == "integer" else float(value)
            except ValueError:
                expected = "整数" if rule.kind == "integer" else "数字"
                return [self._issue(section, key, value, f"应为{expected}")]
            if isinstance(number, float) and not math.isfinite(number):
                return [self._issue(section, key, value, "应为有限数字")]
            if rule.minimum is not None and number < rule.minimum:
                return [
                    self._issue(
                        section,
                        key,
                        value,
                        f"不能小于 {rule.minimum:g}",
                    )
                ]
            if rule.maximum is not None and number > rule.maximum:
                return [
                    self._issue(
                        section,
                        key,
                        value,
                        f"不能大于 {rule.maximum:g}",
                    )
                ]
            return []

        if rule.kind == "enum":
            if value not in rule.choices:
                return [
                    self._issue(
                        section,
                        key,
                        value,
                        _choice_message(rule.choices, _suggest(value, rule.choices)),
                    )
                ]
            return []

        if rule.kind == "list":
            items = [item.strip() for item in value.split(",") if item.strip()]
            invalid = [item for item in items if item not in rule.choices]
            if not items:
                return [self._issue(section, key, value, "至少需要填写一个值")]
            if invalid:
                invalid_value = invalid[0]
                return [
                    self._issue(
                        section,
                        key,
                        value,
                        f'"{invalid_value}" 无效；'
                        + _choice_message(
                            rule.choices,
                            _suggest(invalid_value, rule.choices),
                        ),
                    )
                ]
            if len(items) != len(set(items)):
                return [self._issue(section, key, value, "不能包含重复值")]
            return []

        if rule.kind == "times":
            invalid = [
                item.strip()
                for item in value.split(",")
                if item.strip()
                and not re.fullmatch(
                    r"(?:[01]\d|2[0-3]):[0-5]\d",
                    item.strip(),
                )
            ]
            if invalid:
                return [
                    self._issue(
                        section,
                        key,
                        value,
                        f'"{invalid[0]}" 格式错误，应为 HH:MM，多个时间用英文逗号分隔',
                    )
                ]
            return []

        if rule.kind == "timezone":
            try:
                pytz.timezone(value)
            except pytz.UnknownTimeZoneError:
                return [
                    self._issue(
                        section,
                        key,
                        value,
                        "不是有效的 IANA 时区，例如 Asia/Shanghai",
                    )
                ]
            return []

        if rule.kind == "public_url":
            try:
                parts = urlsplit(value)
                if (
                    parts.scheme not in {"http", "https"}
                    or not parts.hostname
                    or parts.username
                    or parts.password
                    or parts.query
                    or parts.fragment
                ):
                    raise ValueError
                _ = parts.port
            except ValueError:
                return [
                    self._issue(
                        section,
                        key,
                        value,
                        "应为完整的 HTTP(S) 地址，例如 https://iptv.example.com",
                    )
                ]
            return []

        if rule.kind == "resolution":
            match = re.fullmatch(r"(\d+)[xX*](\d+)", value)
            if not match or any(int(part) <= 0 for part in match.groups()):
                return [
                    self._issue(
                        section,
                        key,
                        value,
                        "应为有效分辨率，例如 1920x1080",
                    )
                ]
            return []

        if rule.kind == "resolution_speed_map":
            issues = []
            for item in value.split(","):
                parts = item.split(":", 1)
                if len(parts) != 2 or not re.fullmatch(
                    r"\d+[xX*]\d+",
                    parts[0].strip(),
                ):
                    issues.append(
                        self._issue(
                            section,
                            key,
                            value,
                            f'"{item.strip()}" 格式错误，应为 分辨率:速率',
                        )
                    )
                    continue
                width, height = re.split(r"[xX*]", parts[0].strip())
                if int(width) <= 0 or int(height) <= 0:
                    issues.append(
                        self._issue(
                            section,
                            key,
                            value,
                            f'"{item.strip()}" 的分辨率必须大于 0',
                        )
                    )
                    continue
                try:
                    speed = float(parts[1].strip())
                    if not math.isfinite(speed) or speed < 0:
                        raise ValueError
                except ValueError:
                    issues.append(
                        self._issue(
                            section,
                            key,
                            value,
                            f'"{item.strip()}" 的速率应为不小于 0 的数字',
                        )
                    )
            return issues

        return []

    def validate(self):
        issues = []
        known_sections = {"Settings"}
        for section in self.config.sections():
            if section not in known_sections:
                issues.append(
                    ConfigIssue(
                        self._source(section, ""),
                        section,
                        None,
                        None,
                        "未知配置分组",
                    )
                )
                continue
            for key, value in self.config.items(section, raw=True):
                rule = CONFIG_SCHEMA.get(key)
                if rule is None:
                    suggestion = difflib.get_close_matches(
                        key,
                        CONFIG_SCHEMA,
                        n=1,
                        cutoff=0.6,
                    )
                    message = "未知配置项"
                    if suggestion:
                        message += f'；是否想填写 "{suggestion[0]}"？'
                    issues.append(self._issue(section, key, None, message))
                    continue
                issues.extend(self._validate_value(section, key, value, rule))

        if self.config.has_section("Settings"):
            min_value = get_resolution_value(
                self.config.get("Settings", "min_resolution", fallback="")
            )
            max_value = get_resolution_value(
                self.config.get("Settings", "max_resolution", fallback="")
            )
            if min_value and max_value and min_value > max_value:
                issues.append(
                    self._issue(
                        "Settings",
                        "max_resolution",
                        self.config.get("Settings", "max_resolution"),
                        "不能小于 min_resolution",
                    )
                )

            if self.config.getboolean("Settings", "open_rtmp", fallback=True):
                ports = {
                    "app_port": self.app_port,
                    "service_port": self.service_port,
                    "nginx_rtmp_port": self.nginx_rtmp_port,
                }
                duplicates = {
                    port
                    for port in ports.values()
                    if list(ports.values()).count(port) > 1
                }
                for key, port in ports.items():
                    if port in duplicates:
                        issues.append(
                            self._issue(
                                "Settings",
                                key,
                                str(port),
                                "开启 RTMP 时，内部 API、HTTP 服务和 RTMP 端口不能相同",
                            )
                        )

        public_port = self._environ.get("PUBLIC_PORT")
        if public_port is not None:
            try:
                parsed_public_port = int(public_port)
                if not 1 <= parsed_public_port <= 65535:
                    raise ValueError
            except (TypeError, ValueError):
                issues.append(
                    ConfigIssue(
                        "环境变量 PUBLIC_PORT",
                        None,
                        "PUBLIC_PORT",
                        str(public_port),
                        "应为 1～65535 的整数",
                    )
                )

        if issues:
            raise ConfigValidationError(issues)

    def set(self, section, key, value):
"""
[PT-BR]         Set the config
"""
        self.config.set(section, key, value)
        self._sources[(section, key)] = "运行时配置"

    def save(self):
"""
[PT-BR]         Save config with write
"""
        self.validate()
        user_config_path = self._user_config_path
        if not os.path.exists(user_config_path):
            user_config_dir = os.path.dirname(user_config_path)
            if user_config_dir:
                os.makedirs(user_config_dir, exist_ok=True)
        with open(user_config_path, "w", encoding="utf-8") as configfile:
            self.config.write(configfile)

    def copy(self, path="config"):
"""
[PT-BR]         Copy config files to current directory
"""
        dest_folder = os.path.join(os.getcwd(), path)
        try:
            src_dir = (
                os.path.join(sys._MEIPASS, path)
                if getattr(sys, "frozen", False)
                else resource_path(path)
            )
            if os.path.exists(src_dir):
                if not os.path.exists(dest_folder):
                    os.makedirs(dest_folder, exist_ok=True)

                for root, _, files in os.walk(src_dir):
                    for file in files:
                        src_file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(src_file_path, src_dir)
                        dest_file_path = os.path.join(dest_folder, relative_path)

                        dest_file_dir = os.path.dirname(dest_file_path)
                        if not os.path.exists(dest_file_dir):
                            os.makedirs(dest_file_dir, exist_ok=True)

                        if not os.path.exists(dest_file_path):
                            shutil.copy(src_file_path, dest_file_path)
        except Exception as e:
            print(f"Failed to copy files: {str(e)}")


config = ConfigManager()
