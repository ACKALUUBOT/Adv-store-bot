
import importlib
import logging
from pathlib import Path

logger = logging.getLogger("PluginsLoader")


def load_plugins():
    """plugins फ़ोल्डर की सभी .py फ़ाइलों को स्वचलित (dynamically) लोड करता है।"""
    plugins_dir = Path(__file__).parent

    # सभी .py फ़ाइलें निकालें (सख्त फ़िल्टर: __init__.py और private/hidden फ़ाइलों को छोड़कर)
    plugin_files = [
        f
        for f in plugins_dir.glob("*.py")
        if not f.name.startswith(("_", "."))
    ]

    for file in plugin_files:
        module_name = file.stem  # फ़ाइल का नाम बिना .py एक्सटेंशन के
        try:
            importlib.import_module(f"plugins.{module_name}")
            logger.info(f"✅ Plugin Loaded: plugins.{module_name}")
        except Exception as e:
            logger.error(
                f"❌ Failed to load plugin plugins.{module_name}: {e}",
                exc_info=True,
            )


# `plugins` पैकेज इम्पोर्ट होते ही ऑटो-लोड एक्ज़ीक्यूट होगा
load_plugins()
