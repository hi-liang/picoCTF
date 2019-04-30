"""Tests for the /api/problem/ routes."""

from .common import (
  clear_db,
  client,
  decode_response,
  enable_sample_problems,
  ensure_within_competition,
  get_conn,
  get_csrf_token,
  load_sample_problems,
  problems_endpoint_response,
  register_test_accounts,
  USER_DEMOGRAPHICS
)


def test_problems(client):
    """Tests the /problems endpoint."""
    clear_db()
    register_test_accounts()

    # Test without logging in
    res = client.get('/api/problems')
    status, message, data = decode_response(res)
    assert status == 0
    assert message == 'You must be logged in'

    # Test without any loaded problems
    client.post('/api/user/login', data={
        'username': USER_DEMOGRAPHICS['username'],
        'password': USER_DEMOGRAPHICS['password'],
        })

    res = client.get('/api/problems')
    status, message, data = decode_response(res)
    assert status == 1
    assert data == []

    # Test after loading sample problems
    # Should still display none as disabled problems are filtered out
    load_sample_problems()
    res = client.get('/api/problems')
    status, message, data = decode_response(res)
    assert status == 1
    assert data == []

    # Test after enabling sample problems
    enable_sample_problems()
    res = client.get('/api/problems')
    status, message, data = decode_response(res)
    assert status == 1
    for i in range(len(data)):
        # Cannot compare randomly templated fields with e.g. port numbers
        for field in {
            'author', 'category', 'disabled', 'hints', 'name', 'organization',
            'pid', 'sanitized_name', 'score', 'server', 'server_number',
            'socket', 'solved', 'solves', 'unlocked'
        }:
            assert data[i][field] == problems_endpoint_response[i][field]


def test_submit(client):
    """Test the /problems/submit endpoint."""
    clear_db()
    register_test_accounts()
    load_sample_problems()
    enable_sample_problems()
    ensure_within_competition()

    # Test without being logged in
    res = client.post('/api/problems/submit', data={})
    status, message, data = decode_response(res)
    assert status == 0
    assert message == 'You must be logged in'

    # Test without CSRF token
    client.post('/api/user/login', data={
        'username': USER_DEMOGRAPHICS['username'],
        'password': USER_DEMOGRAPHICS['password'],
        })

    res = client.post('/api/problems/submit', data={})
    status, message, data = decode_response(res)
    assert status == 0
    assert message == 'CSRF token not in form'
    csrf_t = get_csrf_token(res)

    # Test submitting a solution to an invalid problem
    res = client.post('/api/problems/submit', data={
        'token': csrf_t,
        'pid': 'invalid',
        'key': 'incorrect',
        'method': 'testint'
    })
    status, message, data = decode_response(res)
    assert status == 0
    assert message == "You can't submit flags to problems you haven't " + \
                      "unlocked."

    # Test submitting an incorrect solution to a valid problem
    res = client.get('/api/problems')
    status, message, data = decode_response(res)
    unlocked_pids = [problem['pid'] for problem in data]

    res = client.post('/api/problems/submit', data={
        'token': csrf_t,
        'pid': unlocked_pids[0],
        'key': 'incorrect',
        'method': 'testing'
    })
    status, message, data = decode_response(res)
    assert status == 0
    assert message == 'That is incorrect!'

    # Test submitting the correct solution
    db = get_conn()
    assigned_instance_id = db.teams.find_one({
        'team_name': USER_DEMOGRAPHICS['username']
    })['instances'][unlocked_pids[0]]
    problem_instances = db.problems.find_one({
        'pid': unlocked_pids[0]
    })['instances']
    assigned_instance = None
    for instance in problem_instances:
        if instance['iid'] == assigned_instance_id:
            assigned_instance = instance
            break
    correct_key = assigned_instance['flag']

    res = client.post('/api/problems/submit', data={
        'token': csrf_t,
        'pid': unlocked_pids[0],
        'key': correct_key,
        'method': 'testing'
    })
    status, message, data = decode_response(res)
    assert status == 1
    assert message == 'That is correct!'

    # Test submitting the correct solution a second time
    res = client.post('/api/problems/submit', data={
        'token': csrf_t,
        'pid': unlocked_pids[0],
        'key': correct_key,
        'method': 'testing'
    })
    status, message, data = decode_response(res)
    assert status == 1
    assert message == 'Flag correct: however, you have already ' + \
                      'solved this problem.'

    # Test submitting an incorrect solution a second time
    # @TODO cases where another team member has solved
    res = client.post('/api/problems/submit', data={
        'token': csrf_t,
        'pid': unlocked_pids[0],
        'key': 'incorrect',
        'method': 'testing'
    })
    status, message, data = decode_response(res)
    assert status == 0
    assert message == 'Flag incorrect: please note that you have ' + \
                      'already solved this problem.'
