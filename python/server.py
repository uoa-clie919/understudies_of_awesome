from badges import Badges
import requests

from json import dumps

import decouple
import time
import csv
from datetime import datetime, timedelta

from oauthlib.common import urldecode
from oauthlib.oauth2 import WebApplicationClient
from requests_oauthlib import OAuth2Session

from flask import Flask, request, redirect, session, render_template

# To prevent errors while running on localhost over HTTP rather than HTTPS
import os

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

#user1000003 = Badges()
user = Badges()
app = Flask(__name__)
# Host and IP for the local server, running on http://host:port
HOST = decouple.config("HOST")
PORT = decouple.config("PORT")

# YOUR CLIENT CREDENTIALS CONFIG
CLIENT_ID = decouple.config("CLIENT_ID")
CLIENT_SECRET = decouple.config("CLIENT_SECRET")


REDIRECT_URI = f"http://{HOST}:{PORT}/callback"
AUTH_URL = decouple.config("AUTH_URL")
TOKEN_URL = decouple.config("TOKEN_URL")
API_URL = decouple.config("API_URL")

# Your scopes, list of strings
scope = decouple.config("SCOPES", cast=lambda v: [s.strip() for s in v.split(',')])

# An unguessable random string. It is used to protect against CSRF attacks.
state = "super-secret-state"

# Today's date
date = "2019-12-14"



# API endpoints
SESSION_ENDPOINT = f"{API_URL}/session/"
CONSUMPTION_SUMMARY_ENDPOINT = f"{API_URL}/consumption/summary/"+"{}/{}/?start_date=2019-12-14&end_date=2019-12-18"
CONSUMPTION_AVERAGE_ENDPOINT = f"{API_URL}/consumption/averages/"+"{}/{}/?start_date=2019-12-10&end_date=2019-12-14"


@app.route("/")
def authorization():
    """User Authorization.
    Redirect the user/resource owner to our OAuth provider
    While supplying key OAuth parameters.
    """
    # Here we're using `WebApplicationClient` to utilize authorization code grant
    client = WebApplicationClient(client_id=CLIENT_ID)
    request_uri = client.prepare_request_uri(
        AUTH_URL, redirect_uri=REDIRECT_URI, scope=scope, state=state
    )
    # State is used to prevent CSRF, we'll keep it to reuse it later.
    session["oauth_state"] = state
    return redirect(request_uri)


@app.route("/callback", methods=["GET"])
def callback():
    """Retrieving an access token.
    After you've redirected from our provider to your callback URL,
    you'll have access to the auth code in the redirect URL, which
    we'll be using to get an access token.
    """

    client = WebApplicationClient(client_id=CLIENT_ID)
    # Parse the response URI after the callback, with the same state we initially sent
    client.parse_request_uri_response(
        request.url, state=session["oauth_state"])
    # Now we've access to the auth code
    code = client.code

    # Prepare request body to get the access token
    body = client.prepare_request_body(
        code=code,
        redirect_uri=REDIRECT_URI,
        include_client_id=False,
        scope=scope,
    )

    # Basic HTTP auth by providing your client credentials
    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)

    # Making a post request to the TOKEN_URL endpoint
    r = requests.post(TOKEN_URL, data=dict(urldecode(body)), auth=auth)

    # Parse the response to get the token and store it in session
    token = client.parse_request_body_response(r.text, scope=scope)
    session["access_token"] = token

    return redirect("/home")


@app.route("/home", methods=["GET"])
def home():
    # Redirect user to auth endpoint if access token is missing
    if session.get("access_token", None) is None:
        return redirect("/")
    return """
    <h1>Access token obtained!</h1>
    <ul>
        <li><a href="/sample_api_calls">Sample API calls</a></li>
    </ul>
    """


@app.route("/sample_api_calls", methods=["GET"])
def sample_api_calls():
    # Redirect user to auth endpoint if access token is missing
    if session.get("access_token", None) is None:
        return redirect("/")

    # /session/ call
    # Create an OAuth2Session with the access token we've previously obtained
    oauth_session = OAuth2Session(token=session["access_token"])
    # GET request to sessions end point
    response = oauth_session.get(SESSION_ENDPOINT)

    # Prepare data for summary end point
    # Get customer data
    customer = response.json()["data"]["customer"][0]
    # Get customer number
    customer_number = customer["customer_number"]
    # Get get customer's connection ID
    connection_id = customer["connection"]["connection_id"]

    # /consumption/summary/customer_number/connection_id/ call
    # summary_response = oauth_session.get(
    #     CONSUMPTION_SUMMARY_ENDPOINT.format(customer_number, connection_id)
    #     # params = {'start_date':'2017-12-14', 'end_date':'2017-12-18'}
    # )

    # wait a bit, to prevent error of too many requests
    time.sleep(1)

    # GET customer's consumption averages
    averages_response = oauth_session.get(
        CONSUMPTION_AVERAGE_ENDPOINT.format(customer_number, connection_id)
    )

    # Retrieve customer points data for last seven days
    f = open('customer_points_csv.txt')
    points_data = csv.reader(f)
    next(points_data) #skip header in csv file
    # Sort data by date
    points_data = sorted(points_data, key = lambda row: datetime.strptime(row[1], "%Y-%m-%d"), reverse=True)
    data_updated_flag = False
    # Check if data needs to be uploaded
    for row in points_data:
        if int(row[0]) == int(customer_number):
            if str(row[1]) == date:
                # today's date
                data_updated_flag = True
                break
            if datetime.strptime(row[1], "%Y-%m-%d") == datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1):
                # yesterday, update with today's data
                n_points,p_points = pointCalculations(averages_response,date)
                f.close()
                with open('customer_points_csv.txt', 'a') as fd:
                    fd.write(customer_number + ',' + date + ',' + str(n_points + p_points) + ',' + str(n_points / 10) + ',' + str(p_points / 10))
                data_updated_flag = True
                break
            else:
                # historical data must be uploaded
                f.close()
                with open('customer_points_csv.txt', 'a') as fd:
                    for d in averages_response.json()["data"]["usage"]:
                        n_points,p_points = pointCalculations(averages_response, d)
                        fd.write("\n" + str(customer_number) + "," + date + "," + str(n_points + p_points) + "," + str(n_points / 10) + "," + str(p_points / 10))
                data_updated_flag = True
                break
    if data_updated_flag == False:
        # historical data must be uploaded
        f.close()
        with open('customer_points_csv.txt', 'a') as fd:
            for d in averages_response.json()["data"]["usage"]:
                n_points,p_points = pointCalculations(averages_response, d)
                fd.write("\n" + str(customer_number) + "," + date + "," + str(n_points + p_points) + "," + str(n_points / 10) + "," + str(p_points / 10))
        data_updated_flag = True

    # Add daily points from last seven days to array
    f = open('customer_points_csv.txt')
    points_data = csv.reader(f)
    next(points_data) #skip header in csv file
    # Sort data by date
    points_data = sorted(points_data, key = lambda row: datetime.strptime(row[1], "%Y-%m-%d"), reverse=True)
    seven_day_points = [["days ago", 0.0, 0.0]] * 7   
    i = 0 #index seven_day_points array
    for row in points_data:
        if int(row[0]) == int(customer_number):
            seven_day_points[i] = ["{} days ago".format(i), float(row[2]), float(20)]
            i = i + 1
        if i >= 7:
            break    

    # Calculate total points
    total_points = 0.0
    for row in points_data:
        if int(row[0]) == int(customer_number): # check if correct customer
            total_points = total_points + float(row[2])

    # Carbon emissions
    carbon_emissions = float(seven_day_points[0][1]) / 10 * 0.1287 / 1000
    user.checkLogInBadge()
    user.checkMilestone2Badge(total_points)
    user.checkMilestone3Badge(total_points)
    user.checkMilestoneBadge(total_points)
    user.checkXmasBadge()

    bad1 = user.getBadge(1)
    bad2 = user.getBadge(2)
    bad3 = user.getBadge(3)

    return render_template('./web.html', points = total_points, carbon= carbon_emissions,
     pointGraph = seven_day_points , badge1 = bad1, badge2 = bad2, badge3 = bad3 )
    
    # """
    #     <h1>/session/ response</h1>
    #     <div>%s</div>
    #     <h1>consumption averages</h1>
    #     <div>%s</div>
    #     <h1>negative points</h1>
    #     <div>%s</div>
    #     <h1>positive points</h1>
    #     <div>%s</div>
    #     <h1>sorted daily points</h1>
    #     <div>%s</div>
    # """ % (
    #     dumps(response.json(), indent=3),
    #     # dumps(summary_response.json(), indent=3),
    #     dumps(averages_response.json(), indent=3),
    #     negPoints,
    #     customer_number,
    #     seven_day_points
    # )

def pointCalculations(averages_response,day):
    npoints=0
    ppoints =0
    for i in averages_response.json()["data"]["usage"][day]["intervals"]:
        amount = averages_response.json()["data"]["usage"][day]["intervals"][i]["consumption"]
        hour = averages_response.json()["data"]["usage"][day]["intervals"][i]["time"]
        hour = hour[0]

        if hour == "6" or hour == "7" or hour == "8":
            npoints = npoints + 10*float(amount)
        else:
            ppoints = ppoints + 10*float(amount)
    return npoints,ppoints


if __name__ == "__main__":
    app.secret_key = "super secret key"
    app.config["SESSION_TYPE"] = "filesystem"
    app.debug = True
    app.run(host=HOST, port=PORT)

