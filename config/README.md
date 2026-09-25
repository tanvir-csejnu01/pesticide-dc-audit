# Configuration Files

The `config/` folder contains the settings used by the data processing and
audit scripts. Keeping these settings separately makes the workflow easier to
review and reproduce.

- `audit_config.yaml` contains the main settings for the national 84-analyte
  audit, including the expected dataset scope, study period, Data Companion
  comparison period, and statistical analysis settings.

- `environmental_matching_config.yaml` contains the settings used to retrieve
  and match the six environmental variables with pesticide sampling
  activities, including variable definitions, units, matching rules, and
  allowable time windows.