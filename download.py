import concurrent.futures
from simple_salesforce import Salesforce
import requests
import os.path
import csv
import logging

def split_into_batches(items, batch_size):
    full_list = list(items)
    for i in range(0, len(full_list), batch_size):
        yield full_list[i:i + batch_size]


def create_filename(title, file_extension, content_document_id, output_directory):
    # Create filename
    bad_chars = [';', ':', '!', "*", '/', '\\']
    clean_title = filter(lambda i: i not in bad_chars, title)
    clean_title = ''.join(list(clean_title))
    filename = "{0}{1} {2}.{3}".format(output_directory, content_document_id, clean_title, file_extension)
    return filename

def get_content_document_ids(sf, output_directory, query):
    outputFiles = os.path.join(output_directory, 'files/')
    
    # Locate/Create output directories
    if not os.path.isdir(output_directory):
        os.mkdir(output_directory)

    if not os.path.isdir(outputFiles):
        os.mkdir(outputFiles)

    results_path = output_directory + 'files.csv'
    content_document_ids = set()
    content_documents = sf.query_all(query)

    # Save results file with file mapping and return ids
    with open(results_path, 'w', encoding='UTF-8', newline='') as results_csv:
        filewriter = csv.writer(results_csv, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)

        filewriter.writerow(['OwnerId', 'Old_OwnerId',
                            'ContentDocumentId', 'Old_ContentDocumentId',
                            'CreatedById', 'Old_CreatedById', 
                            'LastModifiedById', 'Old_LastModifiedById',
                            'CreatedDate', 'LastModifiedDate', 
                            'SharingPrivacy', 'VersionData', 'PathOnClient', 'Title'])

        for content_document in content_documents["records"]:
            content_document_ids.add(content_document["ContentDocumentId"])
            filename = create_filename(content_document["ContentDocument"]["Title"],
                                       content_document["ContentDocument"]["FileExtension"],
                                       content_document["ContentDocumentId"],
                                       outputFiles)

            filewriter.writerow(
                ['', content_document["ContentDocument"]["OwnerId"],
                 '', content_document["ContentDocumentId"],
                 '', content_document["ContentDocument"]["CreatedById"],
                 '', content_document["ContentDocument"]["LastModifiedById"],
                 content_document["ContentDocument"]["CreatedDate"],content_document["ContentDocument"]["LastModifiedDate"], 
                 content_document["ContentDocument"]["SharingPrivacy"], filename, filename, content_document["ContentDocument"]["Title"]])

    return content_document_ids

def get_content_document_links(sf, output_directory, query, valid_content_document_ids=None, batch_size=100):
    results_path = output_directory + 'links.csv'

    if valid_content_document_ids:
        with open(results_path, 'w', encoding='UTF-8', newline='') as results_csv:
            filewriter = csv.writer(results_csv, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            filewriter.writerow(['ContentDocumentId', 'Old_ContentDocumentId', 'LinkedEntityId', 'Old_LinkedEntityId', 'ShareType', 'Visibility'])
        
            # Divide the full list of files into batches of 200 ids
            batches = list(split_into_batches(valid_content_document_ids, batch_size))

            i = 0
            for batch in batches:
                i = i + 1
                logging.info("Processing batch for links {0}/{1}".format(i, len(batches)))

                # build the query
                final_query = query + ' WHERE ContentDocumentId in (' + ",".join("'" + item + "'" for item in batch) + ')'

                content_documents_links = sf.query_all(final_query)

                # Save results file with file links
                for content_document_link in content_documents_links["records"]:
                    filewriter.writerow(
                        ['', content_document_link["ContentDocumentId"], '', content_document_link["LinkedEntityId"], content_document_link["ShareType"], content_document_link["Visibility"]])


def download_file(args):
    record, output_directory, sf = args
    outputFiles = os.path.join(output_directory, 'files/')
    filename = create_filename(record["Title"], record["FileExtension"], record["ContentDocumentId"], outputFiles)
    url = "https://%s%s" % (sf.sf_instance, record["VersionData"])

    logging.debug("Downloading from " + url)
    response = requests.get(url, headers={"Authorization": "OAuth " + sf.session_id,
                                          "Content-Type": "application/octet-stream"})

    if response.ok:
        # Save File
        with open(filename, "wb") as output_file:
            output_file.write(response.content)
        return "Saved file to %s" % filename
    else:
        return "Couldn't download %s" % url


def fetch_files(sf, query_string, output_directory, valid_content_document_ids=None, batch_size=100):
    # Divide the full list of files into batches of 100 ids
    batches = list(split_into_batches(valid_content_document_ids, batch_size))

    i = 0
    for batch in batches:

        i = i + 1
        logging.info("Processing batch for Files {0}/{1}".format(i, len(batches)))
        batch_query = query_string + ' AND ContentDocumentId in (' + ",".join("'" + item + "'" for item in batch) + ')'
        query_response = sf.query(batch_query)
        records_to_process = len(query_response["records"])
        logging.debug("Content Version Query found {0} results".format(records_to_process))

        while query_response:
            with concurrent.futures.ProcessPoolExecutor() as executor:
                args = ((record, output_directory, sf) for record in query_response["records"])
                for result in executor.map(download_file, args):
                    logging.debug(result)
            break

        logging.debug('All files in batch {0} downloaded'.format(i))
    logging.info('All batches complete')


def main():
    import argparse
    import configparser

    parser = argparse.ArgumentParser(description='Export ContentVersion (Files) from Salesforce')
    parser.add_argument('-q', '--query', metavar='query', required=True,
                        help='SOQL to limit the valid ContentDocumentIds. Must return the Ids of parent objects.')
    args = parser.parse_args()

    # Get settings from config file
    config = configparser.ConfigParser(interpolation=None)
    config.read('download.ini')

    username = config['salesforce']['username']
    password = config['salesforce']['password']
    token = config['salesforce']['security_token']
    batch_size = int(config['salesforce']['batch_size'])
    is_sandbox = config['salesforce']['connect_to_sandbox']
    include_notes = config['salesforce']['include_notes']
    custom_where = config['salesforce']['custom_where']
    file_extensions = config['salesforce']['file_extensions']
    loglevel = logging.getLevelName(config['salesforce']['loglevel'])
    output = config['salesforce']['output_dir']

    # set log level
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=loglevel)

    # queries
    content_document_query = 'SELECT ContentDocumentId, LinkedEntityId, ContentDocument.Title, ' \
                             'ContentDocument.FileExtension, ContentDocument.CreatedById, ContentDocument.CreatedDate, ' \
                             'ContentDocument.LastModifiedById, ContentDocument.LastModifiedDate, ContentDocument.OwnerId, ' \
                             'ContentDocument.SharingPrivacy FROM ContentDocumentLink ' \
                             'WHERE LinkedEntityId in ({0})'.format(args.query)

    content_document_links_query = 'SELECT ContentDocumentId, LinkedEntityId, ShareType, Visibility FROM ContentDocumentLink'

    files_query = 'SELECT ContentDocumentId, Title, VersionData, FileExtension FROM ContentVersion WHERE IsLatest = True'
    
    # Domain
    domain = None
    
    # Sandbox
    if is_sandbox == 'True':
        domain = 'test'

    # Include Notes
    if include_notes == 'False':
        files_query += " AND FileExtension != 'snote'"
        content_document_query += " AND ContentDocument.FileExtension != 'snote'"

    # File Extensions
    if file_extensions != 'All':
        if include_notes == 'True': 
            file_extensions += ",'snote'"

        files_query += " AND FileExtension in ({0})".format(file_extensions)
        content_document_query += " AND ContentDocument.FileExtension in ({0})".format(file_extensions)

    # Custom where
    if custom_where:
        files_query += " {0}".format(custom_where)
        content_document_query += " {0}".format(custom_where)

    # Output
    logging.info('Export ContentVersion (Files) from Salesforce')
    logging.info('Username: ' + username)
    logging.info('Output directory: ' + output)

    # Connect
    sf = Salesforce(username=username, password=password, security_token=token, domain=domain)
    logging.info("Connected successfully to {0}".format(sf.sf_instance))

    # Get Content Document Ids
    logging.info("Querying to get Content Document Ids..." )
    valid_content_document_ids = None
    if content_document_query:
        valid_content_document_ids = get_content_document_ids(sf=sf, output_directory=output,
                                                              query=content_document_query)
    logging.info("Found {0} total files".format(len(valid_content_document_ids)))

    # Get Content Document Links
    logging.info("Querying to get Content Document Links...")
    if content_document_links_query:
        get_content_document_links(sf=sf, output_directory=output, query=content_document_links_query, valid_content_document_ids=valid_content_document_ids)
    logging.info("Links file created Successfully")

    # Begin Downloads
    fetch_files(sf=sf, query_string=files_query, valid_content_document_ids=valid_content_document_ids,
                output_directory=output, batch_size=batch_size)


if __name__ == "__main__":
    main()
