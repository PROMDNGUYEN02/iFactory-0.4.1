from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect everything from dependency_injector
datas, binaries, hiddenimports = collect_all("dependency_injector")

# Ensure all submodules are included
hiddenimports += collect_submodules("dependency_injector")

# Explicitly add known modules
hiddenimports += [
    "dependency_injector",
    "dependency_injector.errors",
    "dependency_injector.providers",
    "dependency_injector.containers",
    "dependency_injector.wiring",
    "dependency_injector.ext",
    "dependency_injector.ext.aiohttp",
    "dependency_injector.ext.flask",
]
