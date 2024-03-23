This repository contains code for generating VOLTTRON agent configuration based on Haystack tags. 
Currently there is config generator for 

1. Platform Driver Agent 
2. AirsideRCx Agent
3. AirsideEconomizer Agent

# Currently supported device types:

1. AHU
2. VAV

# Currently supported datasources for haystack tags

1. Postgres database that contains haystack tags for equipments, and points.  
2. Json format files - one for equipment tags and one for point tags

# Running config generators
1. Clone source code:
   ```
   git clone https://github.com/VOLTTRON/tag-based-deployment
   cd tag-based-deployment
   ```
2. Install virtual environment
   You can install these parsers either on system python (for example, when using docker containers exclusively for this) or 
   install in a virtual environment when you are using a environment shared with other projects. 
   Creating virtual environment is highly recommended.
   To create a virtual environment and activate it for use run the command in the root directory of this project
   ```
   python3 -m venv ./.venv
   source .venv/bin/activate
   ```
3. Install parsers
   ```
   cd config_generators
   python setup.py install
   ```
4. If your haystack tags are stored in postgresql database, you need to install python postgresql connector
   ```
   pip install psycopg2
   ```
5. Create configuration files for the parser that you want to run. Example configurations are available under configurations directory
6. Run parser
   1. To generate platform driver configurations using haystack tags stored in json file
      ```
      config-gen-json.driver <path to parser's configuration file>
      ```
   2. To generate platform driver configurations using haystack tags stored in postgres db 
      ```
      config-gen-db.driver <path to parser's configuration file>
      ```
   3. To generate airsidercx agent configurations using haystack tags stored in json file
      ```
      config-gen-json.airsidercx <path to parser's configuration file>
      ```
   4. To generate airsidercx agent configurations using haystack tags stored in postgres db 
      ```
      config-gen-db.airsidercx <path to parser's configuration file>
      ```
   5. To generate airside economizer agent configurations using haystack tags stored in json file
      ```
      config-gen-json.airsideeconomizer <path to parser's configuration file>
      ```
   6. To generate airside economizer agent configurations using haystack tags stored in postgres db 
      ```
      config-gen-db.airsideeconomizer <path to parser's configuration file>
      ```
   7. Output:
         1. Generated config files will be in the path provided in configuration. 
         2. Relative path is relative to the directory from which the command is run. 
         3. If no output path is provided in configuration file, then by default output gets written to 
            <execution directory>/<site name>_<config type>_configs
            - Driver configs will be in <execution directory>/<site name>_driver_configs
            - AirsideRcx configs will be in <execution directory>/<site name>_airsidercx_configs
            - AirsideEconomizer configs will be in <execution directory>/<site name>_airside_economizer_configs
         4. Details of all devices that couldn't be processed will be recorded in a file called 
            "unmapped_device_details" in the output directory
   

# Platform Driver configuration generator classes:

1. DriverConfigGenerator: Base class that parses the configuration
2. IntellimationDriverConfigGenerator: Derives from DriverConfigGenerator and reads haystack tags from Intellimation 
   postgres database and generates platform driver configurations for AHUs and VAVs. 
3. JsonDriverConfigGenerator: Derives from DriverConfigGenerator and reads haystack tags from two json files - 
   one for equipment tags and one for point tags - and generates driver configurations for AHUs and VAVs

## Configuration for DriverConfigGenerator
The configuration file for this config generator script consists of four types of data
1. metadata - that gives the details of where the haystack data is stored and how to access it
2. Optional site, campus and building details that can be used to query data and also generate volttron topic names 
   prefix for devices
3. Configuration template - a json object that contains a template driver configuration based on driver type. 
   ConfiGenerator code looks for variables/string patterns in this string and replace it with device specific details 
   for generating individual device configuration
4. Optional output directory into which generated configurations are written. If provided code will try create the 
   directory provided and save generated configurations in it. Relative path are relative to path from which the 
   config generator script is run. If this configuration is not provided, default to 
   "<site name>_driver_configs" driver directory under the code execution directory

Below is an example configuration for  IntellimationDriverConfigGenerator where metadata is in a postrgres database
```
 {
     "metadata": {
        "connection_params": {
                "dbname": "intellimation",
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "password": "volttron"
            },
        "equip_table": "equipment",
        "point_table": "points"
        },

     # If provided query will be filtered using this condition
     "site_id": "r:intellimation.dc_dgs.dcps.ojs",


     # Optional campus. If not provided will be parsed from site_id else will be empty. defaults to empty
     # "campus": "dcps",
     
     # Optional building or site name. If not provided parsed from site_id if site_id is provided. defaults to empty
     # "building": "",
     
     # optional driver topic_prefix. By default devices/<campus>/<building/site>/<device>/<subdevice>,
     # if campus and building information is not provided through site id, or (campus, building) or topic_prefix then
     # topic would be of the format devices/<device>/<subdevice>
     "topic_prefix": "devices/WDC/OJS",

     # where generated configs should be saved. Code will try to do makedir -p
     "output_dir": "/home/volttron/git/intellimation/tag_based_setup/output/local_brookland_config",

     # Template for driver configuration
     "config_template": {
              "driver_type": "normalgw",
              "driver_config": {
                "point_service": "localhost:8080",
                "bacnet_service": "localhost:8080",
                "priority": 14,
                
                # if device id is unique, use the below nf query format
                #"query": "@period:[1, +inf]  @attr_device_id:[{device_id},{device_id}]",

                # query format when device id is not unique and both device id and obj_name are required to uniquely
                # identify a device
                "query": "@period:[1, +inf] @attr_device_id:[{device_id},{device_id}] @attr_prop_object_name: {obj_name}",

                "topic_name_format": "object_name:{prop_object_name}"
              },
              "interval": 60
            }
 }
```
If the haystack tags are parsed from a json file, the metadata value in the above configuration can be changed to
```
"metadata": {
        "equip_json": "/path/to/json/Sitename_EQUIP_haystack.json",
        "points_json": "/path/to/json/Sitename_POINTS_haystack.json"
        }
```

Sample configurations can be found [here](configurations/driver)
## Running driver config generator
   1. Use the command ```config-gen-json.driver <path to file>``` or ```config-gen-db.driver <path to file>```. 
   2. One driver config json file is created for each ahu and all the associated vavs
   3. Vavs not mapped to a AHU get their configurations written to a separate unmapped_vavs.json
   4. Details of devices that cannot be processed correctly get written to 'unmapped_device_details' file

# AirsideRCx configuration generator classes:

1. AirsideRCxConfigGenerator: Base class that parses the configuration
2. IntellimationAirsideRCxConfigGenerator: Derives from AirsideRCxConfigGenerator and reads haystack tags 
   from Intellimation postgres database and generates a AirsideRcx agent configuration for each AHU with one or more 
   VAVs. AHUs without VAVs are not included
3. JsonAirsideRCxConfigGenerator: Derives from AirsideRCxConfigGenerator and reads haystack tags from two json files 
   - one for equipment tags and one for point tags - and generates a AirsideRcx agent configuration for each AHU 
    with one or more VAVs. AHUs without VAVs are not included


##Configuration for AirsideRCxConfigGenerator
The configuration file for this config generator script consists of four types of data
1. metadata - that gives the details of where the haystack data is stored and how to access it
2. Optional site, campus and building details that can be used to query data and also generate volttron topic names 
   prefix for devices
3. Mandatory point metadata - 
   1. information on which field contains the point type information. For example, each point's type could be stored in 
      a haystack "dis" field.
   2. mapping of agent point type to haystack point type. For example, the point that has "fan_status" information 
      could have the metadata "SaFanCmd" in "dis" field of the point.
4. Configuration template - a json object that contains a template airsidercx configuration. 
   ConfiGenerator code inserts the campus, building, AHU, its vavs, and the point name details in this template and 
   generates one AirsideRCx config for each AHU
5. Optional output directory into which generated configurations are written. If provided code will try to create the 
   directory provided and save generated configurations in it. Relative path are relative to path from which the 
   config generator script is run. If this configuration is not provided, default to 
   "<site name>_airsidercx_configs" directory under the code execution directory

Below is an example configuration for  IntellimationAirsideRCxConfigGenerator where metadata is in a postrgres database
```
  {
     "metadata": {
        "connection_params": {
                "dbname": "intellimation",
                "host": "127.0.0.1",
                "port": 5432,
                "user": "postgres",
                "password": "volttron"
            },
        "equip_table": "equipment",
        "point_table": "points"
        },
     "site_id": "r:intellimation.dc_dgs.dcps.brookland_ms",
     # optional. if not provided will be derived from site_id.split('.')[-2]
     #"campus": "dcps",
     # optional. if not provided will be derived from site_id.split('.')[-1]
     #"building": "brookland_ms",

     # metadata value to indentity the specific points and hence its name in this setup
     "point_meta_map": {
            "fan_status": "s:SaFanCmd",
            "zone_reheat": "s:RhtVlvPos",
            "zone_damper": "s:DmpCmd",
            "duct_stcpr": "s:SaPress",
            "duct_stcpr_stpt": "s:SaPressSp",
            "sa_temp": "s:SaTemp",
            "fan_speedcmd": "s:SaFanSpdCmd",
            "sat_stpt": "s:SaTempSp"
        },
     # The field that contains the above point metadata
     "point_meta_field": "dis",

     "output_dir":"output/brookland_aircx_configs",
     "config_template": {
        "analysis_name": "AirsideAIRCx",
        "device": {

        },
        "actuation_mode": "passive",
        "arguments": {
            "point_mapping": {

            }
            #### Uncomment to customize thresholds (thresholds have single #)
            #### If uncommenting any parameters below add a comma after point_mapping
            #### and remove any trailing commas to make it a valid json
            #### Only uncommented lines will get written into generated config
            # "no_required_data": 10,
            # "sensitivity": custom

            ### auto_correct_flag can be set to false, "low", "normal", or "high" ###
            # "auto_correct_flag": false,
            #"warm_up_time": 5,

            ### data_window - time duration for data collection prior to analysis_name
            ### if data_window is ommitted from configuration defaults to run on the hour.

            ### Static Pressure AIRCx Thresholds ###
            # "stcpr_stpt_deviation_thr": 20
            # "warm_up_time": 5,
            # "duct_stcpr_retuning": 0.1,
            # "max_duct_stcpr_stpt": 2.5,
            # "high_sf_thr": 95.0,
            # "low_sf_thr": 20.0,
            # "zn_high_damper_thr": 90.0,
            # "zn_low_damper_thr": 10.0,
            # "min_duct_stcpr_stpt": 0.5,
            # "hdzn_damper_thr": 30.0,

            ### SAT AIRCx Thresholds ###
            # "sat_stpt_deviation_thr": 5,
            # "percent_reheat_thr": 25.0,
            # "rht_on_thr": 10.0,
            # "sat_high_damper_thr": 80.0,
            # "percent_damper_thr": 60.0,
            # "min_sat_stpt": 50.0,
            # "sat_retuning": 1.0,
            # "reheat_valve_thr": 50.0,
            # "max_sat_stpt": 75.0,

            #### Schedule/Reset AIRCx Thresholds ###
            # "unocc_time_thr": 40.0,
            # "unocc_stcpr_thr": 0.2,
            # "monday_sch": ["5:30","18:30"],
            # "tuesday_sch": ["5:30","18:30"],
            # "wednesday_sch": ["5:30","18:30"],
            # "thursday_sch": ["5:30","18:30"],
            # "friday_sch": ["5:30","18:30"],
            # "saturday_sch": ["0:00","0:00"],
            # "sunday_sch": ["0:00","0:00"],

            # "sat_reset_thr": 5.0,
            # "stcpr_reset_thr": 0.25
        }
    }
 }

```
If the haystack tags are parsed from a json file, the metadata value in the above configuration can be changed to
```
"metadata": {
        "equip_json": "/path/to/json/Sitename_EQUIP_haystack.json",
        "points_json": "/path/to/json/Sitename_POINTS_haystack.json"
        }
```
Sample configurations can be found [here](configurations/airsidercx)

**Note:**

 All the commented fields in the config_template or optional AirsideRCx configuration parameters and the commented 
 values are the default values used by the AirsideRCx agent. If you would like to uncomment and include any of these 
 parameters in your generated configurations, please make sure you add or remove any trailing commas to make the value 
 of "config_template" a valid json string. Commented line are for informational purpose only. None of the commented 
 lines will be in the final generated configuration.

## Running AirsideRCx config generator
   1. Use the command ```config-gen-json.airsidercx <path to file>``` or ```config-gen-db.airsidercx <path to file>```. 
   2. One config json file is created for each ahu and all the associated vavs
   3. For an AHU either fan_status or fan_speedcmd point is mandatory for airsidercx
   4. If a duct_stcpr or zone_damper point is not found, a warning message is generated
   5. Details of devices that cannot be processed correctly, and warning messages get written to the 
      'unmapped_device_details' file

# AirsideEconomizer configuration generator classes:

1. AirsideEconomizerConfigGenerator: Base class that parses the configuration
2. IntellimationAirsideEconomizerConfigGenerator: Derives from AirsideEconomizerConfigGenerator and reads haystack tags 
   from Intellimation postgres database and generates a AirsideEconomizer agent configuration for each AHU 
3. JsonAirsideEconomizerConfigGenerator: Derives from AirsideRCxConfigGenerator and reads haystack tags from two json  
   files, one for equipment tags and one for point tags and generates a AirsideEconomizer agent configuration for each  
   AHU

## Configuration for AirsideEconomizerConfigGenerator

The configuration file for this config generator script consists of four types of data
1. metadata - that gives the details of where the haystack data is stored and how to access it
2. Optional site, campus and building details that can be used to query data and also generate volttron topic names 
   prefix for devices
3. Mandatory point metadata - 
   1. information on which field contains the point type information. For example, each point's type could be stored in 
      a haystack "dis" field.
   2. mapping of agent point type to haystack point type. For example, the point that has "supply_fan_status"  
      information could have the metadata "SaFanCmd" in "dis" field of the point.
4. Configuration template - a json object that contains a template airside economizer configuration. 
   ConfiGenerator code inserts the campus, building, AHU, and the point name details in this template and 
   generates one AirsideEconomizer agent config for each AHU
5. Optional output directory into which generated configurations are written. If provided code will try to create the 
   directory provided and save generated configurations in it. Relative path are relative to path from which the 
   config generator script is run. If this configuration is not provided, default to 
   "<site name>_airside_economizer_configs" directory under the code execution directory

Below is an example configuration for  IntellimationAirsideRCxConfigGenerator where metadata is in a postrgres database
```
  {
     "metadata": {
        "connection_params": {
                "dbname": "intellimation",
                "host": "127.0.0.1",
                "port": 5432,
                "user": "postgres",
                "password": "volttron"
            },
        "equip_table": "equipment",
        "point_table": "points"
        },
     "site_id": "r:intellimation.dc_dgs.dcps.brookland_ms",
     # optional. if not provided will be derived from site_id.split('.')[-2]
     #"campus": "dcps",
     # optional. if not provided will be derived from site_id.split('.')[-1]
     #"building": "brookland_ms",

     # metadata value to indentity the specific points and hence its name in this setup
     "point_meta_map": {
            "fan_status": "s:SaFanCmd",
            "zone_reheat": "s:RhtVlvPos",
            "zone_damper": "s:DmpCmd",
            "duct_stcpr": "s:SaPress",
            "duct_stcpr_stpt": "s:SaPressSp",
            "sa_temp": "s:SaTemp",
            "fan_speedcmd": "s:SaFanSpdCmd",
            "sat_stpt": "s:SaTempSp"
        },
     # The field that contains the above point metadata
     "point_meta_field": "dis",

     "output_dir":"output/brookland_aircx_configs",
     "config_template": {
        "device": {

        },
        "analysis_name": "Economizer_AIRCx",
        "actuation_mode": "passive",
        "arguments": {
            "point_mapping": {

            },
            "device_type": "ahu",
            "data_window": 30,
            "no_required_data": 10,
            "open_damper_time": 0,
            "low_supply_fan_threshold": 20.0,
            "mat_low_threshold": 50.0,
            "mat_high_threshold": 90.0,
            "oat_low_threshold": 30.0,
            "oat_high_threshold": 100.0,
            "rat_low_threshold": 50.0,
            "rat_high_threshold": 90.0,
            "temp_difference_threshold": 4.0,
            "open_damper_threshold": 90.0,
            "oaf_temperature_threshold": 4.0,
            "cooling_enabled_threshold": 5.0,
            "minimum_damper_setpoint": 10.0,
            "desired_oaf": 10.0,
            "rated_cfm": 1000.0,
            "eer": 10.0,
            "economizer_type": "DDB",
            "temp_band": 1.0
        }
     }
 }

```
If the haystack tags are parsed from a json file, the metadata value in the above configuration can be changed to
```
"metadata": {
        "equip_json": "/path/to/json/Sitename_EQUIP_haystack.json",
        "points_json": "/path/to/json/Sitename_POINTS_haystack.json"
        }
```
Sample configurations can be found [here](configurations/airside_economizer)


## Running AirsideEconomizer config generator
   1. Use the command ```config-gen-json.airsideeconomizer <path to file>``` or ```config-gen-db.airsideeconomizer <path to file>```. 
   2. One config json file is created for each ahu
   3. All points specified under point mapping are mandatory for AirsideEconomizer
   4. Details of devices that cannot be processed correctly, and warning messages get written to the 
      'unmapped_device_details' file


# Extending config generators

These config generators use certain parsing logic specific to Intellimation sites. For example, how a device name is 
parsed and used to query data from a device using a normal framework driver interface is specific to Intellimation, 
however the base class and the child classes are structured such that the code can be easily extended for other 
sites that use different driver interface and database store for storing haystack tags. 
For example, a site that uses a bacnet driver can change the config_template in the configuration and override only 
the variable substitution code in a subclass. A site that stores haystack tags in different datastore can export the 
data in json format, subclass the JsonDriverConfigGenerator, reuse the json parsing logic to get list of ahus and vavs 
but override just the logic for variable substitution in config_template 
