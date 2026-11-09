"""Select and prepare the desktop application's persistent data directory."""

import os
import sys
import tempfile
from pathlib import Path


DATA_DIRECTORY_ENV = "IPTV_API_DATA_DIR"
DATA_DIRECTORY_OPTION = "--data-dir"
DATA_DIRECTORY_SETTING = "runtime/data_directory"


class RuntimeDirectoryError(RuntimeError):
"""




[PT-BR] def _take_directory_option(argv: list[str]) -> str | None:

[PT-BR]     for index, value in enumerate(tuple(argv)):

[PT-BR]         if value == DATA_DIRECTORY_OPTION:

[PT-BR]             if index + 1 >= len(argv) or not argv[index + 1].strip():

[PT-BR]                 raise RuntimeDirectoryError(f"{DATA_DIRECTORY_OPTION} 需要指定目录")

[PT-BR]             directory = argv[index + 1]

[PT-BR]             del argv[index:index + 2]

[PT-BR]             return directory

[PT-BR]         if value.startswith(f"{DATA_DIRECTORY_OPTION}="):

[PT-BR]             directory = value.partition("=")[2].strip()

[PT-BR]             if not directory:

[PT-BR]                 raise RuntimeDirectoryError(f"{DATA_DIRECTORY_OPTION} 需要指定目录")

[PT-BR]             del argv[index]

[PT-BR]             return directory

[PT-BR]     return None





[PT-BR] def _writable_directory(path: Path) -> bool:

[PT-BR]     try:

[PT-BR]         path.mkdir(parents=True, exist_ok=True)

[PT-BR]         with tempfile.NamedTemporaryFile(dir=path, prefix=".iptv-api-write-", delete=True):

[PT-BR]             pass

[PT-BR]         return True

[PT-BR]     except OSError:

[PT-BR]         return False





[PT-BR] def validate_runtime_directory(directory: str | os.PathLike[str]) -> Path:

[PT-BR]     path = Path(directory).expanduser().resolve()

[PT-BR]     if not _writable_directory(path):

[PT-BR]         raise RuntimeDirectoryError(f"数据目录不可写：{path}")

[PT-BR]     return path





[PT-BR] def default_runtime_directory(

[PT-BR]     *,

[PT-BR]     fallback_directory: str | os.PathLike[str] | None = None,

[PT-BR]     frozen: bool | None = None,

[PT-BR]     executable: str | os.PathLike[str] | None = None,

[PT-BR]     prefer_executable_directory: bool = True,

[PT-BR] ) -> Path:

[PT-BR]     frozen = getattr(sys, "frozen", False) if frozen is None else frozen

[PT-BR]     if not frozen:

[PT-BR]         return Path.cwd().resolve()

[PT-BR]     if frozen and prefer_executable_directory:

[PT-BR]         directory = Path(executable or sys.executable).resolve().parent

[PT-BR]         if _writable_directory(directory):

[PT-BR]             return directory

[PT-BR]     if fallback_directory is not None:

[PT-BR]         return validate_runtime_directory(fallback_directory)

[PT-BR]     raise RuntimeDirectoryError("未找到可用的数据目录")





[PT-BR] def prepare_runtime_directory(

[PT-BR]     argv: list[str],

[PT-BR]     *,

[PT-BR]     fallback_directory: str | os.PathLike[str] | None = None,

[PT-BR]     environ: dict[str, str] | None = None,

[PT-BR]     frozen: bool | None = None,

[PT-BR]     executable: str | os.PathLike[str] | None = None,

[PT-BR]     prefer_executable_directory: bool = True,

[PT-BR]     saved_directory: str | os.PathLike[str] | None = None,

[PT-BR] ) -> Path | None:
"""

    An explicit command-line option or environment variable takes precedence.
    Frozen applications otherwise prefer their executable directory and use the
    supplied system data-directory fallback only when that location is locked.
    """
    environ = os.environ if environ is None else environ
    option_directory = _take_directory_option(argv)
    requested_directory = option_directory or environ.get(DATA_DIRECTORY_ENV, "").strip()
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    directory_validated = False

    if requested_directory:
        directory = Path(requested_directory).expanduser().resolve()
        explicit = True
    elif saved_directory:
        directory = Path(saved_directory).expanduser().resolve()
        explicit = False
    elif frozen:
        directory = default_runtime_directory(
            fallback_directory=fallback_directory,
            frozen=frozen,
            executable=executable,
            prefer_executable_directory=prefer_executable_directory,
        )
        explicit = False
        directory_validated = True
    else:
        return None

    if not directory_validated and not _writable_directory(directory):
        if explicit or fallback_directory is None:
            raise RuntimeDirectoryError(f"数据目录不可写：{directory}")
        directory = Path(fallback_directory).expanduser().resolve()
        if not _writable_directory(directory):
            raise RuntimeDirectoryError(f"数据目录不可写：{directory}")

    os.chdir(directory)
    environ[DATA_DIRECTORY_ENV] = str(directory)
    return directory
