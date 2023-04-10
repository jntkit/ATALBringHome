import boto3
import json
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from collections import Counter
from flask import Flask, render_template, request, Response,redirect
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io,os
import base64
import pandas as pd
import pytz

# Get the absolute path to the templates folder
templates_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))

# Set the template folder for Flask app
app = Flask(__name__, template_folder=templates_dir)

votes = []



# Set up S3 client
s3 = boto3.client('s3'  ,
    aws_access_key_id='AKIA565FYRLK5VQIY6MV',
    aws_secret_access_key='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',
    region_name='us-east-1')

# Name of the S3 bucket to use
bucket_name = 'travel-preference'

# Create the bucket if it doesn't exist
try:
    s3.head_bucket(Bucket=bucket_name)
except ClientError:
    s3.create_bucket(Bucket=bucket_name)

# Set up S3 resource
s3_resource = boto3.resource('s3')
bucket = s3_resource.Bucket(bucket_name)


# Define list of countries
COUNTRIES = ['Japan', 'Korea', 'Singapore', 'Thailand', 'Malaysia', 'Vietnam']

@app.route('/')
def index():
    selected_countries = request.args.getlist('countries')
    return render_template('index.html', countries=COUNTRIES, selected_countries=selected_countries)


@app.route('/submit', methods=['POST'])
def submit_vote():
    selected_countries = request.form.getlist('countries')
    timestamp = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
    timestamp_name = datetime.now().strftime('%Y%m%d%H%M%S%f')
    vote_data = {"Selected":f"{selected_countries}",
            "Timestamp":f"{timestamp}"
            }
    vote_data = json.dumps(vote_data).encode('utf-8')
    # vote_data = f'Timestamp: {timestamp}\nSelected countries: {selected_countries}'.encode('utf-8')
    s3.put_object(
        Bucket=f'{bucket_name}',
        Key=f'votes/{timestamp_name}',
        Body= vote_data
    )
    return redirect('/results')

@app.route('/results')
def results():
    # List all objects in the "votes" folder
    response = s3.list_objects(Bucket=bucket_name, Prefix='votes/')
    votes = []
    if 'Contents' in response:
        for obj in response['Contents']:
            # Get the vote data from the S3 object
            obj_data = s3.get_object(Bucket=bucket_name, Key=obj['Key'])
            body = obj_data['Body'].read().decode('utf-8')
            if not body:
                continue
            vote = json.loads(body)
            votes.append(vote)

    df = pd.json_normalize(votes)
    for country_option in COUNTRIES:
        df[f'{country_option}']=df.Selected.apply(lambda x_list : 1 if  f'{country_option}' in x_list else 0)


    # Calculate hour difference from current time
    now = datetime.now()
    # Set timezone of df['Timestamp'] to timezone of now
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%Y-%m-%d_%H:%M:%S')

    # Calculate the difference in hours between the current time and each vote
    df['THAT_HOUR'] = (now - df['Timestamp']).astype('timedelta64[h]')


    # Calculate total number of participants
    num_participants = len(df)

    # Calculate number of countries selected
    num_countries = df[COUNTRIES].sum().sum()

    # Calculate total number of votes
    total_votes = df[COUNTRIES].sum()

    # Calculate top 3 favorite countries
    top_3_countries = list(total_votes.nlargest(3).index)

    # Create pie chart for vote distribution in last 24 hours
    num_participants_24 =  len(df[df["THAT_HOUR"]<24])
    total_votes_24 = df[df["THAT_HOUR"]<24][COUNTRIES].sum()

    # Calculate vote percentages for each country
    vote_percentages = {}
    for country in COUNTRIES:
        votes_for_country = total_votes_24[country]
        percentage = round(votes_for_country / num_participants_24 * 100, 1)
        vote_percentages[country] = percentage

    vote_counts = [f'{count} ({(count/total_votes_24.sum()*100):.1f}%)' for count in total_votes_24]
    plt.figure(figsize=(6, 6))
    labels = [f'{country} ({votes:,d} - {percentage:.1f}%)' for country, votes, percentage in zip(COUNTRIES, total_votes_24, vote_percentages.values())]
    plt.pie(total_votes_24, labels=labels, autopct='', textprops={'fontsize': 12})
    plt.title('Vote Distribution in last 24 hours')
    plt.legend(loc='best')


    # Save chart image to a local file in the templates/static/images folder
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    chart_path = os.path.join(static_dir, 'P_24z_chart.png')
    plt.savefig(chart_path, format='png')
    print("Outuput")
    print(chart_path)

    # Generate HTML template and pass variables
    return render_template('results.html',
                           num_participants=num_participants,
                           num_countries=num_countries,
                           total_votes=total_votes,
                           top_3_countries=top_3_countries,
                           chart_path = chart_path ,
                           vote_percentages=vote_percentages)

if __name__ == '__main__':
    app.run(debug=False)
