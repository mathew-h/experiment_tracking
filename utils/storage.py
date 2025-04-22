import os
import boto3
from google.cloud import storage
from azure.storage.blob import BlobServiceClient, BlobClient
from config.storage import get_storage_config

def save_file(file_data, file_name, folder="general"):
    """Save a file to the configured storage system."""
    config = get_storage_config()
    
    if config["type"] == "s3":
        return save_to_s3(file_data, file_name, folder, config)
    elif config["type"] == "gcs":
        return save_to_gcs(file_data, file_name, folder, config)
    elif config["type"] == "azure":
        return save_to_azure(file_data, file_name, folder, config)
    else:
        return save_to_local(file_data, file_name, folder, config)

def get_file(file_path):
    """Retrieve a file from the configured storage system."""
    config = get_storage_config()
    
    if file_path.startswith("s3://"):
        return get_from_s3(file_path, config)
    elif file_path.startswith("gcs://"):
        return get_from_gcs(file_path, config)
    elif file_path.startswith("https://") and "blob.core.windows.net" in file_path:
        return get_from_azure(file_path, config)
    elif config["type"] == "azure":
        print("Warning: Retrieving Azure file based on config type and relative path. Storing full URL is recommended.")
        return get_from_azure(file_path, config)
    else:
        return get_from_local(file_path, config)

def delete_file(file_path):
    """Delete a file from the configured storage system."""
    config = get_storage_config()
    
    if file_path.startswith("s3://"):
        delete_from_s3(file_path, config)
    elif file_path.startswith("gcs://"):
        delete_from_gcs(file_path, config)
    elif file_path.startswith("https://") and "blob.core.windows.net" in file_path:
        delete_from_azure(file_path, config)
    elif config["type"] == "azure":
        print("Warning: Deleting Azure file based on config type and relative path. Storing full URL is recommended.")
        delete_from_azure(file_path, config)
    else:
        delete_from_local(file_path, config)

def save_to_s3(file_data, file_name, folder, config):
    """Save a file to AWS S3."""
    s3_client = boto3.client(
        's3',
        aws_access_key_id=config['aws_access_key_id'],
        aws_secret_access_key=config['aws_secret_access_key'],
        region_name=config['region']
    )
    
    key = f"{folder}/{file_name}"
    s3_client.put_object(
        Bucket=config['bucket'],
        Key=key,
        Body=file_data
    )
    
    return f"s3://{config['bucket']}/{key}"

def get_from_s3(file_path, config):
    """Retrieve a file from AWS S3."""
    s3_client = boto3.client(
        's3',
        aws_access_key_id=config['aws_access_key_id'],
        aws_secret_access_key=config['aws_secret_access_key'],
        region_name=config['region']
    )
    
    # Remove s3:// prefix if present
    key = file_path.replace(f"s3://{config['bucket']}/", "")
    response = s3_client.get_object(
        Bucket=config['bucket'],
        Key=key
    )
    
    return response['Body'].read()

def delete_from_s3(file_path, config):
    """Delete a file from AWS S3."""
    s3_client = boto3.client(
        's3',
        aws_access_key_id=config['aws_access_key_id'],
        aws_secret_access_key=config['aws_secret_access_key'],
        region_name=config['region']
    )
    
    # Remove s3:// prefix if present
    key = file_path.replace(f"s3://{config['bucket']}/", "")
    s3_client.delete_object(
        Bucket=config['bucket'],
        Key=key
    )

def save_to_gcs(file_data, file_name, folder, config):
    """Save a file to Google Cloud Storage."""
    storage_client = storage.Client.from_service_account_json(config['credentials_path'])
    bucket = storage_client.bucket(config['bucket'])
    
    key = f"{folder}/{file_name}"
    blob = bucket.blob(key)
    blob.upload_from_string(file_data)
    
    return f"gcs://{config['bucket']}/{key}"

def get_from_gcs(file_path, config):
    """Retrieve a file from Google Cloud Storage."""
    storage_client = storage.Client.from_service_account_json(config['credentials_path'])
    bucket = storage_client.bucket(config['bucket'])
    
    # Remove gcs:// prefix if present
    key = file_path.replace(f"gcs://{config['bucket']}/", "")
    blob = bucket.blob(key)
    
    return blob.download_as_bytes()

def delete_from_gcs(file_path, config):
    """Delete a file from Google Cloud Storage."""
    storage_client = storage.Client.from_service_account_json(config['credentials_path'])
    bucket = storage_client.bucket(config['bucket'])
    
    # Remove gcs:// prefix if present
    key = file_path.replace(f"gcs://{config['bucket']}/", "")
    blob = bucket.blob(key)
    blob.delete()

def save_to_azure(file_data, file_name, folder, config):
    """Save file_data to Azure Blob Storage."""
    try:
        if 'connection_string' not in config or 'container' not in config:
             raise ValueError("Azure storage config missing connection_string or container")

        blob_service_client = BlobServiceClient.from_connection_string(config['connection_string'])
        blob_name = f"{folder.strip('/')}/{file_name.strip('/')}"
        blob_client = blob_service_client.get_blob_client(container=config['container'], blob=blob_name)

        print(f"Uploading to Azure Blob Storage: Container='{config['container']}', Blob='{blob_name}'")
        blob_client.upload_blob(file_data, overwrite=True)

        print(f"Upload successful. URL: {blob_client.url}")
        return blob_client.url

    except Exception as e:
        print(f"ERROR saving to Azure: {e}")
        raise

def get_from_azure(file_path, config):
    """Retrieve a file from Azure Blob Storage using its URL or blob name."""
    try:
        if file_path.startswith("https://") and "blob.core.windows.net" in file_path:
             blob_client = BlobClient.from_blob_url(file_path)
        else:
            if 'connection_string' not in config or 'container' not in config:
                 raise ValueError("Azure storage config missing connection_string or container")
            blob_service_client = BlobServiceClient.from_connection_string(config['connection_string'])
            blob_client = blob_service_client.get_blob_client(container=config['container'], blob=file_path)

        print(f"Downloading from Azure Blob: {blob_client.container_name}/{blob_client.blob_name}")
        download_stream = blob_client.download_blob()
        data = download_stream.readall()
        print(f"Downloaded {len(data)} bytes.")
        return data

    except Exception as e:
        print(f"ERROR getting from Azure: {e}")
        raise

def delete_from_azure(file_path, config):
    """Delete a file from Azure Blob Storage using its URL or blob name."""
    try:
        if file_path.startswith("https://") and "blob.core.windows.net" in file_path:
            blob_client = BlobClient.from_blob_url(file_path)
        else:
             if 'connection_string' not in config or 'container' not in config:
                 raise ValueError("Azure storage config missing connection_string or container")
             blob_service_client = BlobServiceClient.from_connection_string(config['connection_string'])
             blob_client = blob_service_client.get_blob_client(container=config['container'], blob=file_path)

        print(f"Deleting from Azure Blob: {blob_client.container_name}/{blob_client.blob_name}")
        blob_client.delete_blob(delete_snapshots="include")
        print("Deletion successful.")

    except Exception as e:
        print(f"ERROR deleting from Azure: {e}")
        raise

def save_to_local(file_data, file_name, folder, config):
    """Save a file to local storage."""
    folder_path = os.path.join(config['base_path'], folder)
    os.makedirs(folder_path, exist_ok=True)
    
    file_path = os.path.join(folder_path, file_name)
    with open(file_path, 'wb') as f:
        f.write(file_data)
    
    return file_path

def get_from_local(file_path, config):
    """Retrieve a file from local storage."""
    with open(file_path, 'rb') as f:
        return f.read()

def delete_from_local(file_path, config):
    """Delete a file from local storage."""
    if os.path.exists(file_path):
        os.remove(file_path) 