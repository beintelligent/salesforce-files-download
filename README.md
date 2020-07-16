# salesforce-files-download
THIS PROJECT IS FORKED FROM [HERE](https://github.com/snorf/salesforce-files-download)

It has the same behaviour but we just added 
  - An extra option to include notes
  - An extra option to include certain file extensions (comma separated value with single quotes e.g. 'pdf','jpg','gif')

We also improve this README file.

## Prerequisites
- Python locally installed. You can download Python from [here](https://www.python.org/downloads/).
- Free Disk space to handle all the files that you will download.
- This script uses the API to download files so make sure you have less files than the remaining API calls on Salesforce, if not, you will have to split the call by extensions or add more restriction to the query and run it on different days.

## Getting Started
- Download the files from Github clicking [this](https://github.com/beintelligent/salesforce-files-download/archive/master.zip) link or clone the repository `git clone https://github.com/beintelligent/salesforce-files-download.git`
- Go to the folder where you unzip the files or clone the repository:
    1. Run `pip3 install -r requirements.txt`
    2. Copy `download.ini.template` to `download.ini` and fill the following fields:
        - username = The Salesforce username to connect to the org
        - password = The Salesforce password for the previous username
        - security_token = The Salesforce security token of the same username
        - connect_to_sandbox = If we are connecting to a Salesforce Sandbox or not _(False/True)_. Default _False_.
        - output_dir = Directory where the files would be downloaded. Default `C:\Files_Extract\`. Be careful this path only works on Windows.
        - batch_size = The size of the batch to process files. Default _100_.
        - file_extensions= The file extensions of the files to retrieve. Comma separated value with single quotes e.g. 'pdf','jpg','gif'. Defaul _All_.
        - include_notes = If we want to include the Enhanced Notes or not _(False/True)_. Default _False_.
        - loglevel = Level of Python logging. Allowed values [here](https://docs.python.org/3/library/logging.html#logging-levels). Default _INFO_.

## Usage
The script requires a query to filter the Files to export via ContentDocumentLink and LinkedEntityId.

- Launch the script:
    `python download.py -q "SELECT Id FROM Opportunity WHERE Stage = 'Closed - Won'"`