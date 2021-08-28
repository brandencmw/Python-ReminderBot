import discord
from discord.ext import tasks
import os
import boto3
import re
import json
from datetime import datetime
from datetime import timedelta
from RemoveReminder import remove_reminder

client = discord.Client()
bot_triggers = ['!addremind', '!remremind', '!showremind']

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    check_for_reminders.start()

@tasks.loop(minutes=1)
async def check_for_reminders(dynamodb=None):
    channel = client.get_channel(829052528901357581)
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')

    table = dynamodb.Table('Reminders')
    time_string = datetime.now().strftime("%Y-%m-%dT%H:%M:00")
    print(type(time_string))
    scan_kwargs = {
        'TableName': "Reminders",
        'ProjectionExpression': "title, showtime, link, recurring, intervalVerb, intervalLen",
    }

    done = False
    start_key = None
    items = []
    while not done:
        if start_key:
            scan_kwargs['ExclusiveStartKey'] = start_key
        response = table.scan(**scan_kwargs)
        items += response.get('Items', [])
        start_key = response.get('LastEvaluatedKey', None)
        done = start_key is None

    for item in items:
        if item['showtime'] == time_string:
            await channel.send("{}: {}".format(item['title'], item['link']))
            if(item['recurring']):
                update_datetime(item)
            else:
                remove_reminder(item)

def update_datetime(row_info, dynamodb=None):
    showtime = datetime.strptime(row_info['showtime'], '%Y-%m-%dT%H:%M:00')
    interval = int(row_info['intervalLen'])
    if row_info['intervalVerb'] == 'y':
        showtime += timedelta(years=interval)
    elif row_info['intervalVerb'] == 'mo':
        showtime += timedelta(months=interval)
    elif row_info['intervalVerb'] == 'w':
        showtime += timedelta(weeks=interval)
    elif row_info['intervalVerb'] == 'd':
        showtime += timedelta(days=interval)
    elif row_info['intervalVerb'] == 'h':
        showtime += timedelta(hours=interval)
    elif row_info['intervalVerb'] == 'm':
        showtime += timedelta(minutes=interval)
    row_info['showtime'] = showtime.isoformat()
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Reminders')

    response = table.update_item(
        Key={
            'title': row_info['title']
        },
        UpdateExpression='SET showtime = :new_time',
        ExpressionAttributeValues={
            ':new_time': row_info['showtime']
        },
        ReturnValues="UPDATED_NEW"
    )
    print(response)


async def show_reminders(dynamodb=None, title_filter=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')

    channel = client.get_channel(829052528901357581)
    table = dynamodb.Table('Reminders')
    scan_kwargs = {
        'TableName': "Reminders",
        'ProjectionExpression': "title, showtime",
    }

    done = False
    start_key = None
    while not done:
        if start_key:
            scan_kwargs['ExclusiveStartKey'] = start_key
        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])
        await channel.send("You have the following reminders...")
        for item in items:
            await create_message(item, channel)
        start_key = response.get('LastEvaluatedKey', None)
        done = start_key is None

async def create_message(reminder, channel):
    # message = "{} next occuring at {}".format(reminder['title'], reminder['showtime'])
    channel = client.get_channel(829052528901357581)
    await channel.send("{} set to remind you at {}".format(reminder['title'], reminder['showtime']))

#Parses reminder message for info and prints the parts
def add_reminder(row_info, dynamodb=None):
    print(row_info)
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Reminders')
    table.put_item(Item=row_info)
    return

def get_datetime(message):
    if 'recurring' in message:
        datetime_str = ' '.join(message.split()[message.split().index('at')+1:message.split().index('recurring')])
    else:
        datetime_str = ' '.join(message.split()[message.split().index('at')+1:])

    return datetime.strptime(datetime_str, '%H:%M %A, %B %d, %Y')

# def calculate_datetime(message):

def get_interval_verb(message):
    if 'yearly' in message:
        verb = 'y'
    elif 'monthly' in message:
        verb = 'mo'
    elif 'weekly' in message:
        verb = 'w'
    elif 'daily' in message:
        verb = 'd'
    elif 'hourly' in message:
        verb = 'h'
    elif 'minutely' in message:
        verb = 'm'

    return verb

def get_interval_length(message):
    if any(char.isdigit() for char in message):
        return int(re.findall("\d", message)[-1])
    else:
        print("ERROR NEED NUMBER")
        return


def parse_message(message):
    msg_json = {
        "title": None,
        "showtime": None,
        "recurring": False,
        "intervalVerb": None,
        "intervalLen": None,
        "link": None
    }
    split_message = message.split()
    if ' at' in message:
        msg_json['title'] = ' '.join(split_message[1:split_message.index('at')])
    elif ' in' in message:
        msg_json['title'] = ' '.join(split_message[1:split_message.index('in')])
    else:
        msg_json['title'] = ' '.join(split_message[1:])

    if(split_message[0] == '!addremind'):
        msg_json['link'] = split_message.pop()
        msg_json['recurring'] = 'recurring' in split_message
        if ' at' in message: 
            msg_json['showtime'] = get_datetime(' '.join(split_message)).isoformat()
        elif ' in' in message: 
            calculate_datetime(message).isoformat()

        if msg_json['recurring']:
            msg_json['intervalVerb'] = get_interval_verb(message)
            msg_json['intervalLen'] = get_interval_length(message)

    return msg_json

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    
    if any(message.content.startswith(trigger) for trigger in bot_triggers):
        message_json = parse_message(message.content)

        if(message.content.startswith('!addremind')):
            add_reminder(message_json)
        elif message.content.startswith('!remremind'):
            remove_reminder(message_json)
        elif message.content.startswith('!showremind'):
            await show_reminders()


client.run(os.getenv('DISCORD_TOKEN'))

