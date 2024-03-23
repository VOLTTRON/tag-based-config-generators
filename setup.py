from setuptools import setup
from setuptools import find_packages

for package in find_packages():
    print(package)
setup(
    name='intellimation-config-generators',
    version='0.1',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    package_data={
        "volttron.haystack.parser.ilc": ["*.json"],
    },
    url='https://github.com/volttron/intellimation_config_generators',
    license='',
    author='volttron',
    author_email='chandrika@pnnl.gov',
    description='Parsers to generate VOLTTRON agent configurations '
                'based on haystack tags',
    entry_points={
        'console_scripts': [
            'config-gen-db.driver=volttron.haystack.parser.driver.intellimation.config_intellimation:main',
            'config-gen-json.driver=volttron.haystack.parser.driver.json.config_from_json:main',
            'config-gen-db.airsidercx=volttron.haystack.parser.airsidercx.intellimation.config_intellimation:main',
            'config-gen-json.airsidercx=volttron.haystack.parser.airsidercx.json.config_from_json:main',
            'config-gen-db.airsideeconomizer=volttron.haystack.parser.airside_economizer.intellimation.config_intellimation:main',
            'config-gen-json.airsideeconomizer=volttron.haystack.parser.airside_economizer.json.config_from_json:main',
            'config-gen-db.ilc=volttron.haystack.parser.ilc.intellimation.config_intellimation:main',
            'config-gen-json.ilc=volttron.haystack.parser.ilc.json.config_from_json:main',
        ]
    }
)
