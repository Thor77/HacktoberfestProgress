from collections import namedtuple

import requests
from flask import Flask, redirect, render_template, request, session
from flask.ext.session import Session

app = Flask(__name__)
app.config.from_pyfile('config.py')

Session(app)  # set up server-side sessions

client_id = app.config.get('GITHUB_CLIENT_ID')
client_secret = app.config.get('GITHUB_CLIENT_SECRET')

api_base = 'https://api.github.com'

auth_url = 'https://github.com/login/oauth/authorize'\
    '?client_id={}'.format(client_id)

time_range = '2016-10-01T00:00:01Z..2016-10-31T23:59:59'
search_query = 'type:pr+created:' + time_range + '+author:{}'

PullRequest = namedtuple('PullRequest', [
    'url', 'title', 'repo_url', 'repo_name', 'repo_owner'])


class GitHubAPIException(Exception):
    def __init__(self, message, code=None, url=None):
        self.message = message
        self.code = code
        self.url = url


def headers(token):
    '''
    Build authentication-headers with `token`
    '''
    return {
        'Authorization': 'token {}'.format(token),
        'User-Agent': 'HacktoberfestProgress/Thor77'
    }


def authenticated_request(url, token, complete=False):
    '''
    Request `url` authenticated by `token`

    :param url: url/endpoint for the request
    :type url: str

    :param token: auth-token used for the request
    :type token: str

    :param complete: whether the given url is already complete
    :type complete: bool
    '''
    if not complete:
        url = api_base + url
    r = requests.get(url, headers=headers(token))
    if r.status_code != 200:
        return {}
    return r.json()


def fetch_pull_requests(token, username):
    '''
    Fetch pull requests for `username`, authenticated by `token`
    '''
    # requests would urlencode the query so we fill it with a placeholder
    params = {
        'sort': 'created',
        'q': 'QUERY'
    }
    req = requests.Request('GET', api_base + '/search/issues', params=params,
                           headers=headers(token))
    prepared = req.prepare()
    # replace placeholder with actual query
    prepared.url = prepared.url.replace('QUERY', search_query.format(username))
    # send request
    r = requests.Session().send(prepared)
    if r.status_code != 200:
        return []
    return r.json()['items']


@app.errorhandler(GitHubAPIException)
def handle_error(exception):
    '''
    Handle erorr-responses from the GitHub-API
    '''
    return render_template(
        'error.jinja2', description=exception.message, url=exception.url,
        code=exception.code
    )


@app.route('/')
def index():
    if 'access_token' in session:
        return render_template('index.jinja2')
    else:
        return render_template('index.jinja2', auth_url=auth_url)


@app.route('/auth')
def auth():
    if 'access_token' in session:
        return redirect('/progress')
    if request.args.get('error'):
        raise GitHubAPIException(
            message=request.args.get('error_description'),
            code=request.args.get('error'),
            url=request.args.get('error_uri')
        )
    elif request.args.get('code'):
        # obtain access_token
        payload = {
            'code': request.args['code'],
            'client_id': client_id,
            'client_secret': client_secret
        }
        headers = {'Accept': 'application/json'}
        r = requests.post('https://github.com/login/oauth/access_token',
                          data=payload, headers=headers).json()
        if 'error' in r:
            return render_template('error.jinja2')
        elif 'access_token' in r:
            session['access_token'] = r['access_token']
            return redirect('/progress')
    return render_template('progress.jinja2')


@app.route('/progress')
def progress():
    if 'access_token' not in session:
        return redirect('/')
    access_token = session.get('access_token')
    # obtain username
    username = authenticated_request('/user', access_token)['login']
    raw_pull_requests = fetch_pull_requests(access_token, username)

    pull_requests = []
    for pr in raw_pull_requests:
        # fetch details about pull request
        details = authenticated_request(pr['url'], access_token, complete=True)
        # fetch details about repo
        repo = authenticated_request(details['repository_url'], access_token,
                                     complete=True)
        pull_requests.append(
            PullRequest(
                url=pr['html_url'], title=pr['title'],
                repo_name=repo['name'],
                repo_url=repo['html_url'],
                repo_owner=repo['owner']['login']
            )
        )
    return render_template('progress.jinja2', pull_requests=pull_requests)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=7777)
