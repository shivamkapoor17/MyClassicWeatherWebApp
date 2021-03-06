
from flask import Flask, flash, g, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from flask_mail import Mail, Message
import requests
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from requests.exceptions import ConnectionError
from itsdangerous.exc import BadSignature
from itsdangerous.exc import SignatureExpired
import os

app = Flask(__name__)

app.config['SECRET_KEY'] = os.urandom(25)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL')
app.config['MAIL_PASSWORD'] = os.environ.get('PASS')
mail = Mail(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://username:password@localhost/database_name'
db = SQLAlchemy(app)


class User(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    Email = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(80), nullable=False)
    cities = db.relationship('City', backref='user', lazy='dynamic')

class City(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    city_name = db.Column(db.String(20), nullable=False)
    temperature = db.Column(db.String(10), nullable=False)
    icon = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(29), nullable=False)
    datetime = db.Column(db.DateTime)
    user_sno = db.Column(db.Integer, db.ForeignKey('user.sno'), nullable=False)


@app.before_request
def before_request():
    g.user = None
    if 'user' in session:
        g.user = session['user']


@app.route('/')
def index():
    if g.user:
        return redirect(url_for('weather', username=g.user))

    return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if g.user:
        return redirect(url_for('weather', username=g.user))

    if request.method == "POST":
        username = request.form.get('uname')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirmpassword')

        if username == "" or email == "" or password == "" or confirm_password == "":
            flash('You miss some of the entries. Please complete the entries')

        elif password != confirm_password:
            flash('Password fields not matched. Please enter same password in both the password fields')

        else:
            hashed_password = generate_password_hash(password, method='sha256')
            try:
                user = User(username=username, Email=email, password=hashed_password)
                db.session.add(user)
                db.session.commit()
            except IntegrityError:
                flash('Username already exists Please choose different Username ')
            else:
                flash('You are successfully registered', 'success')
                return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('weather', username=g.user))

    if request.method == 'POST':
        username = request.form.get('uname')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            if remember_me == 'on':
                session['user'] = user.username
                session.permanent = True
                return redirect(url_for('weather', username=user.username))
            elif remember_me == None:
                session['user'] = user.username
                session.permanent = False
                return redirect(url_for('weather', username=user.username))

        else:
            flash('Please enter correct Username and Password', 'danger')

    return render_template('login.html')


@app.route('/weather/<string:username>', methods=['GET', 'POST'])
def weather(username):
    if g.user:
        user = User.query.filter_by(username=username).first()

        cities = user.cities
        list_of_cities = []
        for item in cities:
            list_of_cities.append(item.city_name)

        if request.method == 'POST':
            city = request.form.get('city')
            api_key = 'Your_Api_Key'

            if city in list_of_cities:
                flash("Please enter another city", 'info')
                return redirect(url_for('weather', username=username))
            else:
                payload = {'q': city, 'APPID': api_key}
                url = f"https://api.openweathermap.org/data/2.5/weather"

                try:
                    r = requests.get(url, payload)
                except ConnectionError:
                    flash('Please check the Internet connection', 'danger')
                else:
                    json_data = r.json()

                    if json_data['cod'] == 200:
                        temperature = json_data['main']['temp']
                        temperature = round((temperature - 273.15), 3)
                        description = json_data['weather'][0]['description']
                        icon = json_data['weather'][0]['icon']

                        weather = City(city_name=city, temperature=temperature, icon=icon, datetime=datetime.now(), description=description, user=user)
                        db.session.add(weather)
                        db.session.commit()

                    elif json_data['cod'] == '404':
                        flash('Please enter valid city', 'error')

        return render_template('weather.html', username=username, cities=cities)

    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    if g.user:
        session.pop('user', None)

    return redirect(url_for('index'))


@app.route('/update/<string:sno>')
def update(sno):
    if g.user:
        city = City.query.get(sno)
        api_key = 'Your_Api_Key'
        payload = {'q': city.city_name, 'APPID': api_key}
        url = f"https://api.openweathermap.org/data/2.5/weather"
        try:
            r = requests.get(url, payload)
        except ConnectionError:
            flash('Please check the Internet connection', 'info')
        else:
            json_data = r.json()

            temperature = json_data['main']['temp']
            temperature = round((temperature - 273.15), 3)
            description = json_data['weather'][0]['description']
            icon = json_data['weather'][0]['icon']
            dateTime = datetime.now()

            city.temperature = temperature
            city.description = description
            city.icon = icon
            city.datetime = dateTime
            db.session.commit()

    return redirect(url_for('index'))


@app.route('/remove/<string:sno>')
def remove(sno):
    if g.user:
        remove_city = City.query.get(sno)
        db.session.delete(remove_city)
        db.session.commit()

    return redirect(url_for('index'))


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if g.user:
        username = g.user
        user = User.query.filter_by(username=username).first()

        if request.method == 'POST':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if current_password == '' or new_password == '' or confirm_password == '':
                flash('Please fill the form completely!', 'danger')
            elif not check_password_hash(user.password, current_password):
                flash('Current password you have entered is not correct!', 'danger')
            elif new_password != confirm_password:
                flash('New password and confirm password you have entered is not same!', 'danger')
            else:
                new_hashed_password = generate_password_hash(new_password, method='sha256')
                user.password = new_hashed_password
                db.session.commit()
                flash('Your password is changed successfully. Now you can login with your new password', 'success')
                session.pop('user', None)
                return redirect(url_for('login'))

        return render_template('passwordreset.html')

    return redirect(url_for('index'))


@app.route('/password_reset_email', methods=['GET', 'POST'])
def token_generator():
    if g.user:
        return redirect(url_for('weather', username=g.user))

    if request.method == 'POST':
        email = request.form.get('email')
        if email == "":
            flash('You missed to enter your Email', 'danger')
            return redirect(url_for('token_generator'))
        else:
            user = User.query.filter_by(Email=email).first()
            if not user:
                flash('No user found with this email id. You must register first', 'danger')
                return redirect(url_for('token_generator'))
            else:
                s = Serializer(app.config['SECRET_KEY'], 1800)
                token = s.dumps({'user_id': user.sno}).decode('utf-8')
                link = url_for('reset_token', token=token, _external=True)

                msg = Message(subject="Password Reset Request",
                              sender='yourEmail@company.com',
                              recipients=[user.Email])
                msg.body = f'''to reset your password visit the following link:
                {link}
                
                If you did not make this request then simply ignore this email and no changes will be made.
                '''
                try:
                    mail.send(msg)
                except:
                    flash('Your internet connection is failed. Please check the internet connection', 'danger')
                    return redirect(url_for('token_generator'))
                else:
                    flash('Email has been successfully sent on your mail id with password reset information', 'success')
                    return redirect(url_for('login'))

    return render_template('email.html')

def verify_token(token):
    s = Serializer(app.config['SECRET_KEY'])
    try:
        data = s.loads(token)
    except SignatureExpired:
        return 'fizz'
    except BadSignature:
        return 'buzz'
    sno = data['user_id']
    return User.query.get(sno)

@app.route('/password_reset_email/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if g.user:
        return redirect(url_for('weather', username=g.user))

    user = verify_token(token)
    if user == 'fizz':
        flash('The token is Expired. Generate new token', 'warning')
        return redirect(url_for('token_generator'))

    if user == 'buzz':
        flash('The token is Invalid. Generate new token', 'warning')
        return redirect(url_for('token_generator'))

    if request.method == 'POST':
        new_password = request.form.get('newpassword')
        confirm_password = request.form.get('confirmpassword')

        if new_password == '' or confirm_password == '':
            flash('Please fill the form completely!', 'danger')
        elif new_password != confirm_password:
            flash('Put same password in both the password fields', 'danger')
        else:
            new_hashed_password = generate_password_hash(new_password, method='sha256')
            user.password = new_hashed_password
            db.session.commit()
            flash('Your password is changed successfully. Now you can login with your new password', 'success')
            return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)

if __name__=="__main__":
    app.run(debug=True)