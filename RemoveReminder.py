import boto3

def remove_reminder(row_info, dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')

    table = dynamodb.Table('Reminders')
    table.delete_item(
        Key={
            'title': row_info['title']
        }
    )