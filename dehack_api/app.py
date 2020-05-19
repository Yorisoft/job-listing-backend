from flask import Flask
from flask import request
from flask_sqlalchemy import SQLAlchemy
import os
from flask_cors import CORS
from flasgger import Swagger
from flask.json import jsonify

from passlib.hash import sha256_crypt
from flask_mail import Mail
from flask_migrate import Migrate

from flask_jwt import JWT, jwt_required, current_identity

from .utils import activation_email, user_activated_email, reset_password_email


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = 'youremail@email.com'
app.config['MAIL_PASSWORD'] = os.environ['FLASK_MAIL_PASSWORD']
app.config['MAIL_DEFAULT_SENDER'] = 'youremail@email.com'
app.config['MAIL_SUPPRESS_SEND'] = True
app.config['SECRET_KEY'] = 'super-secret'

CORS(app, resources={r"/*": {"origins": "*"}})
swagger = Swagger(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

from .models import User, RegistrationProfile, PasswordReset

def init_db():
    db.create_all()

def truncate_db():
    db.drop_all()

class JwtUser(object):
    id = ""


def default_auth_response_handler(access_token, identity):
    user = User.query.filter_by(id=identity.id).first()
    return jsonify({'access_token': access_token.decode('utf-8'),
                     'first_name': user.first_name, 'last_name': user.last_name})

def authenticate(username, password):

    user = User.query.filter_by(email=username).first()
    if user and sha256_crypt.verify(password, user.password):
        jwtUser = JwtUser()
        jwtUser.id = str(user.id)
        return jwtUser

def identity(payload):
    user_id = payload['identity']
    return User.query.filter_by(id=user_id).first()

jwt = JWT(app, authenticate, identity)

jwt.auth_response_callback = default_auth_response_handler

@app.route('/helloworld')
def hello_world():
    user = User.query.filter_by(id=1).first()
    return jsonify({"msg": "Hello, World!"}), 200

@app.route('/')
def root_view():
    """Endpoint to check api health
    This is using docstrings for specifications.
    ---
    definitions:
      Status:
        type: object
        properties:
          msg:
            type: string
    responses:
      200:
        description: Api health status
        schema:
          $ref: '#/definitions/Status'
    """
    return jsonify({"msg": "Welcome to SweetBread"}), 200


#/users
#HTTP Method: POST
#Create a user object
@app.route('/users', methods=['POST'])
def store_user():
    """Endpoint for creating a user
    This is using docstrings for specifications.
    ---
    parameters:
      - in: body
        name: body
        description: JSON parameters.
        schema:
          properties:
            first_name:
              type: string
              description: First name.
              example: Alice
            last_name:
              type: string
              description: Last name.
              example: Smith
            email:
              type: string
              format: date
              description: Email.
              example: test@email.com
            password:
              type: string
              description: Password.
              example: password
    definitions:
      Status:
        type: object
        properties:
          msg:
            type: string
    responses:
      200:
        description: User created
        schema:
          $ref: '#/definitions/Status'
      400:
        description: Bad request missing post param
        schema:
          $ref: '#/definitions/Status'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/Status'
    """

    content = request.json
    if 'password' in content and 'email' in content and 'first_name' in content and 'last_name' in content:
        try:
            pass_hash = sha256_crypt.hash(content["password"])
            user = User(content["email"], pass_hash, content["first_name"], content["last_name"])
            db.session.add(user)
            db.session.flush()
            registrationProfile = RegistrationProfile(user.id)
            db.session.add(registrationProfile)
            db.session.commit()
            activation_email(user.email, registrationProfile.activation_key, mail)
            return jsonify({"msg": "user created"}), 200
        except Exception:
             return jsonify({"msg": "server error"}), 500
    else:
        return jsonify({"msg": "Bad request"}), 400


#/activate/<activation_key>
#HTTP Method: GET
@app.route('/activate/<string:activation_key>', methods=['GET'])
def activate_user(activation_key):
    """Endpoint for activating a user by using a activation key
    This is using docstrings for specifications.
    ---
    parameters:
      - name: activation_key
        in: path
        type: string
        required: true
    definitions:
      Status:
        type: object
        properties:
          msg:
            type: string
    responses:
      200:
        description: Actiavtion success
        schema:
          $ref: '#/definitions/Status'
      400:
        description: Activation error
        schema:
          $ref: '#/definitions/Status'
    """

    registrationProfile = RegistrationProfile.query.filter_by(activation_key=activation_key).first()
    if bool(registrationProfile) and registrationProfile.used == False:
        user = User.query.filter_by(id=registrationProfile.user_id).first()
        if bool(user):
            user.status = True
            registrationProfile.used = True
            db.session.commit()
            user_activated_email(user.email, mail)
            return jsonify({"msg": "user activated"}), 200
        else:
            return jsonify({"msg": "user activation error"}), 400
    elif bool(registrationProfile) and registrationProfile.used == True:
        return jsonify({"msg": "user activated"}), 200
    else:
        return jsonify({"msg": "user activation error"}), 400


#/getresetkey
#HTTP Method: POST
#Create a user object
@app.route('/getresetkey', methods=['POST'])
def reset_password_request():

    """Endpoint for requesting password reset key
    This is using docstrings for specifications.
    ---
    parameters:
      - in: body
        name: body
        description: JSON parameters.
        schema:
          properties:
            email:
              type: string
              description: Email.
              example: test@email.com
    definitions:
      Status:
        type: object
        properties:
          msg:
            type: string
    responses:
      200:
        description: Password reset setup
        schema:
          $ref: '#/definitions/Status'
      400:
        description: Bad request
        schema:
          $ref: '#/definitions/Status'
    """

    content = request.json
    if 'email' in content:
        user = User.query.filter_by(email=content["email"]).first()
        if bool(user):
            passwordReset = PasswordReset(content["email"])
            db.session.add(passwordReset)
            db.session.commit()
            reset_password_email(content["email"], passwordReset.reset_key, mail)
            return jsonify({"msg": "password reset setup"}), 200
        else:
            return jsonify({"msg": "Bad request"}), 400
    else:
        return jsonify({"msg": "Bad request"}), 400


#/getresetkey
#HTTP Method: POST
#Create a user object
@app.route('/resetpassword/<string:reset_key>', methods=['POST'])
def use_password_reset_key(reset_key):

    """Endpoint for reseting the password
    This is using docstrings for specifications.
    ---
    parameters:
      - in: body
        name: body
        description: JSON parameters.
        schema:
          properties:
            password:
              type: string
              description:  Password.
              example: password
            confirm_password:
              type: string
              description: Pasword.
              example: password
    definitions:
      Status:
        type: object
        properties:
          msg:
            type: string
    responses:
      200:
        description: Password reset
        schema:
          $ref: '#/definitions/Status'
      400:
        description: Bad request
        schema:
          $ref: '#/definitions/Status'
    """

    content = request.json
    if 'password' in content and 'confirm_password' in content:
        resetRow = PasswordReset.query.filter_by(reset_key = reset_key).first()
        if bool(resetRow) and resetRow.used == False:
            user = User.query.filter_by(email=resetRow.email).first()
            if bool(user):
                user.password = sha256_crypt.hash(content["password"])
                resetRow.used = True
                db.session.commit()
                return jsonify({"msg": "password reset"}), 200
            else:
                return jsonify({"msg": "Bad request"}), 400
        else:
            return jsonify({"msg": "Bad request"}), 400
    else:
        return jsonify({"msg": "Bad request"}), 400


@app.route('/protected', methods=["GET"])
@jwt_required()
def protected():

    """Endpoint for testing authenticated request
    This is using docstrings for specifications.
    ---
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
    definitions:
      Status:
        type: object
        properties:
          msg:
            type: string
    responses:
      200:
        description: user email
        schema:
          $ref: '#/definitions/Status'
    """

    #return '%s' % current_identity
    return jsonify({"msg": current_identity.email}), 200


@app.route('/changepassword', methods=["POST"])
@jwt_required()
def change_password():

    """Endpoint for authenticated user change of password
    This is using docstrings for specifications.
    ---
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
      - in: body
        name: body
        description: JSON parameters.
        schema:
          properties:
            current_password:
              type: string
              description: Current Password.
              example: password
            password:
              type: string
              description: New Password.
              example: password
    definitions:
      Status:
        type: object
        properties:
          msg:
            type: string
    responses:
      200:
        description: password changed
        schema:
          $ref: '#/definitions/Status'
      400:
        description: Bad request
        schema:
          $ref: '#/definitions/Status'
    """

    #return '%s' % current_identity
    content = request.json
    if sha256_crypt.verify(content["current_password"], current_identity.password):
        current_identity.password = sha256_crypt.hash(content["password"])
        db.session.commit()
        return jsonify({"msg": "password changed"}), 200
    else:
        return jsonify({"msg": "bad request"}), 400