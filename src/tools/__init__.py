from src.tools.desktop import (
    get_system_vitals,
    list_directory_contents,
    read_text_file,
    control_media,
    set_system_volume,
    launch_application,
    manage_process,
)

ORDIS_TOOLS = [
    get_system_vitals,
    list_directory_contents,
    read_text_file,
    control_media,
    set_system_volume,
    launch_application,
    manage_process,
]

__all__ = ["ORDIS_TOOLS"]