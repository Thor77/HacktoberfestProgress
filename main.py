import requests
from flask import Flask, render_template, request, redirect, session
from collections import namedtuple
from flask.ext.session import Session

app = Flask(__name__)

sess = Session(app)

app = Flask(__name__)

client_id = ''
client_secret = ''

api_base = 'https://api.github.com'

auth_url = 'https://github.com/login/oauth/authorize'\
    '?client_id={}&scope=public_repo'.format(client_id)

PullRequest = namedtuple('PullRequest', [
    'url', 'title', 'repo_url', 'repo_name', 'repo_owner'])


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
        return render_template('error.jinja2',
                               error_code=request.args['error'],
                               error_desc=request.args['error_description'],
                               error_uri=request.args['error_uri'])
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
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }
    r = requests.get(api_base + '/user/issues', headers=headers, params={
        'filter': 'created',
        'state': 'all',
        'since': '2016-10-01T00:00:01Z'
    })
    if r.status_code != 200:
        return render_template('error.jinja2', response=r)
    r = r.json()
    # check for errors
    pull_requests = []
    for issue_or_pr in r:
        if 'pull_request' in issue_or_pr:
            pr = issue_or_pr
            pull_requests.append(
                PullRequest(
                    url=pr['html_url'], title=pr['title'],
                    repo_name=pr['repository']['name'],
                    repo_url=pr['repository']['html_url'],
                    repo_owner=pr['repository']['owner']['login']
                )
            )
    return render_template('progress.jinja2', pull_requests=pull_requests)

if __name__ == '__main__':
    # CHANGE SECRET_KEY!
    app.secret_key = 'N{5K$:6}6>!Y$BxKYBl9gA"*W5&(0X;Xo[Gh)%?Ci@l!EHL]$j4%:Bsv'
    app.config['SESSION_TYPE'] = 'filesystem'

    sess.init_app(app)
    app.run(host='127.0.0.1', port=7777, debug=True)
