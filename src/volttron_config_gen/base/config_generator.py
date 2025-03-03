"""Utility  module to load the right config generator class for a given model name and agent name.
It expects three arguments """
import sys
import pkgutil
import importlib

from volttron_config_gen.edo.file.config_airsidercx import ConfigGenerator

AGENTS = ["driver", "economizer", "airsidercx", "ilc"]
def main():
    if len(sys.argv) != 5:
        print("script requires four argument - "
              "semantic model name, "
              "model data store type"
              "agent name for which configuration is to be generated(driver/economizer/airsidercx/ilc), "
              "path to configuration file to be passed along to the corresponding config generator")
        exit(1)
    semantic_model = sys.argv[1].strip()
    model_data_store = sys.argv[2].strip()
    agent_name = sys.argv[3].strip()
    config_path = sys.argv[4].strip()

    config_gen_package = importlib.import_module("volttron_config_gen")
    model_packages = [name for _, name, ispkg in pkgutil.iter_modules(config_gen_package.__path__) if ispkg]
    model_packages.remove("base")
    model_packages.remove("utils")
    if semantic_model not in model_packages:
        print(f"Currently supported semantic models are {model_packages}")
        exit(1)
    model_package_name = "volttron_config_gen." + semantic_model
    model_package = importlib.import_module(model_package_name)
    model_data_stores =  [name for _, name, ispkg in pkgutil.iter_modules(model_package.__path__) if ispkg]
    if model_data_store not in model_data_stores:
        print(f"Only the following datastore types are supported for {semantic_model}: {model_data_stores}")
        exit(1)
    final_package_name = model_package_name + "." + model_data_store
    if agent_name not in AGENTS:
        print(f"Config generators are currently available only for {AGENTS}")
        exit(1)

    module = importlib.import_module(final_package_name + f".config_{agent_name}")
    GeneratorClass = getattr(module, "ConfigGenerator")
    instance = GeneratorClass(config_path)
    instance.generate_configs()

if __name__ == '__main__':
    main()