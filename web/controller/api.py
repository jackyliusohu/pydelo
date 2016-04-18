# -*- coding:utf-8 -*-
__author__ = 'Rocky Peng'

import traceback
import json
import time
import random
import string
from hashlib import md5

from web.utils.log import Logger
logger = Logger("WEBHOOK")

from web import app
from web.services.users import users
from web.services.hosts import hosts
from web.services.deploys import deploys
from web.services.projects import projects
from web.services.error import Error
from .login import authorize

from flask import request, jsonify, g


#@app.route('/api/deploy/push_events', methods=["POST"])
#@authorize
#def push_events():
#    project = Project(user_id=g.user.get_id())
#    args = request.args.to_dict()
#    data = request.json
#    logger.debug(args)
#    logger.debug(data)
#    # 只针对dev分支进行deploy
#    if data["ref"] == "refs/heads/dev" and data["total_commits_count"] > 0:
#        try:
#            project.start_deploy_by_branch_version(
#                project_id=args["project_id"],
#                host_id=args["host_id"],
#                branch=data["ref"].split("/", 2)[-1],
#                version=data["after"][:7])
#        except Error as err:
#            return jsonify({"rc": err.rc, "err": err.msg}), 406
#        except Exception as err:
#            logger.error(traceback.format_exc())
#            return "ERROR",500
#        else:
#            return jsonify({"rc": 0}), 200
#    else:
#        return jsonify({"rc": 1}), 204

@app.errorhandler(Error)
def error(err):
    return jsonify(dict(rc=err.rc, msg=err.msg))


@app.route("/api/accounts", methods=["PUT"])
@authorize
def api_update_accounts():
    password = request.form.get("password")
    password = md5(password).hexdigest().upper()
    users.update(g.user, password=password)
    return jsonify(dict(rc=0))


@app.route("/api/users/login", methods=["POST"])
def api_user_login():
    username = request.form.get("username")
    password = request.form.get("password")
    sign = users.login(username, password)
    return jsonify(dict(rc=0, data=sign))

@app.route("/api/deploys", methods=["GET"])
@authorize
def api_deploys():
    offset = request.args.get("offset", None, type=int)
    limit = request.args.get("limit", None, type=int)
    if g.user.role == g.user.ROLE["ADMIN"]:
        return jsonify(dict(rc=0,
            data=dict(deploys=deploys.find(offset, limit, order_by="updated_at", desc=True),
                      count=deploys.count())))
    else:
        return jsonify(dict(rc=0,
            data=dict(deploys=deploys.find(offset, limit, order_by="updated_at", desc=True, user_id=g.user.id),
                      count=deploys.count(user_id=g.user.id))))

# @app.route("/api/alldeploys", methods=["GET"])
# @authorize
# def api_alldeploys():
#     offset = request.args.get("offset", None, type=int)
#     limit = request.args.get("limit", None, type=int)
#     return jsonify(dict(rc=0,
#         data=dict(deploys=deploys.all(offset, limit, order_by="updated_at", desc=True),
#                   count=deploys.count())))

@app.route("/api/projects", methods=["GET"])
@authorize
def api_projects():
    offset = request.args.get("offset", None, type=int)
    limit = request.args.get("limit", None, type=int)
    data = users.get_user_projects(g.user)
    return jsonify(dict(rc=0, data=data))

@app.route("/api/projects", methods=["POST"])
@authorize
def api_create_project():
    projects.create(**request.form.to_dict())
    return jsonify(dict(rc=0))

@app.route("/api/projects/<int:id>", methods=["GET"])
@authorize
def api_get_project_by_id(id):
    return jsonify(dict(rc=0, data=projects.get(id)))

@app.route("/api/projects/<int:id>", methods=["PUT"])
@authorize
def api_update_project_by_id(id):
    projects.update(projects.get(id), **request.form.to_dict())
    return jsonify(dict(rc=0))

@app.route("/api/projects/<int:id>/branches", methods=["GET"])
@authorize
def api_project_branches(id):
    projects.git_clone(id)
    return jsonify(dict(rc=0, data=projects.git_branch(id)))

@app.route("/api/projects/<int:id>/branches/<branch>/commits", methods=["GET"])
@authorize
def api_project_branch_commits(id, branch):
    projects.git_clone(id)
    return jsonify(dict(rc=0, data=projects.git_log(id, branch)))

@app.route("/api/deploys", methods=["POST"])
@authorize
def api_post_deploy():
    project_id = request.args.get("project_id")
    host_id = request.args.get("host_id")
    branch = request.form.get("branch")
    commit = request.form.get("commit")
    deploy = deploys.create(
        user_id=g.user.id,
        project_id=project_id,
        host_id=host_id,
        mode=0,
        branch=branch,
        version=commit,
        softln_filename=time.strftime("%Y%m%d-%H%M%S") + "-" + commit,
        )
    deploys.deploy(deploy)
    return jsonify(dict(rc=0, data=dict(id=deploy.id)))

@app.route("/api/deploys/<int:id>", methods=["PUT"])
@authorize
def update_deploy_by_id(id):
    action = request.form.get("action")
    deploy = deploys.get(id)
    deploy.user_id = g.user.id
    if action == "redeploy":
        deploys.deploy(deploy)
        return jsonify({'rc': 0})
    elif action == "rollback":
        deploys.rollback(deploy)
        return jsonify({'rc': 0})
    raise Error(10000, msg=None)

@app.route("/api/deploys/<int:id>", methods=["GET"])
@authorize
def get_deploy_progress_by_id(id):
    deploy = deploys.get(id)
    return jsonify(dict(rc=0, data=deploy))

# 获取所有hosts
@app.route("/api/hosts", methods=["GET"])
@authorize
def api_hosts():
    offset = request.args.get("offset", None, type=int)
    limit = request.args.get("limit", None, type=int)
    data = users.get_user_hosts(g.user)
    return jsonify(dict(rc=0, data=data))

# 获取某个host
@app.route("/api/hosts/<int:id>", methods=["GET"])
@authorize
def api_get_host_by_id(id):
    return jsonify(dict(rc=0, data=hosts.get(id)))

# 更新某个host
@app.route("/api/hosts/<int:id>", methods=["PUT"])
@authorize
def api_update_host_by_id(id):
    hosts.update(hosts.get(id), **request.form.to_dict())
    return jsonify(dict(rc=0))

# 新建host
@app.route("/api/hosts", methods=["POST"])
@authorize
def create_hosts():
    hosts.create(**request.form.to_dict())
    return jsonify(dict(rc=0))

@app.route("/api/users", methods=["POST"])
@authorize
def create_users():
    apikey = ''.join(random.choice(string.letters+string.digits) for _ in range(32))
    users.create(apikey=apikey, **request.form.to_dict())
    return jsonify(dict(rc=0))

@app.route("/api/users", methods=["GET"])
@authorize
def api_users():
    offset = request.args.get("offset", None, type=int)
    limit = request.args.get("limit", None, type=int)
    return jsonify(dict(rc=0, data=dict(users=users.all(offset, limit), count=users.count())))

@app.route("/api/users/<int:id>", methods=["GET"])
@authorize
def api_get_user_by_id(id):
    return jsonify(dict(rc=0, data=users.get(id)))

@app.route("/api/users/<int:id>/hosts", methods=["GET"])
@authorize
def api_get_user_hosts_by_id(id):
    user = users.get(id)
    data = users.get_user_hosts(user)
    return jsonify(dict(rc=0, data=data))

@app.route("/api/users/<int:id>/hosts", methods=["PUT"])
@authorize
def api_update_user_hosts_by_id(id):
    user = users.get(id)
    user.hosts = []
    for host in request.form.getlist("hosts[]"):
        user.hosts.append(hosts.get(int(host)))
    users.save(user)
    return jsonify(dict(rc=0))

@app.route("/api/users/<int:id>/projects", methods=["GET"])
@authorize
def api_get_user_projects_by_id(id):
    user = users.get(id)
    data = users.get_user_projects(user)
    return jsonify(dict(rc=0, data=data))

@app.route("/api/users/<int:id>/projects", methods=["PUT"])
@authorize
def api_update_user_projects_by_id(id):
    user = users.get(id)
    user.projects = []
    for project in request.form.getlist("projects[]"):
        user.projects.append(projects.get(int(project)))
    users.save(user)
    return jsonify(dict(rc=0))

