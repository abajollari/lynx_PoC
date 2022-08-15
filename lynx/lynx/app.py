from flask import Flask, render_template, request, redirect, url_for, flash, session, redirect   
from lynx import create_app, db
from flask_login import current_user
from lynx.services.mail_api import send_email
from flask_babel import Babel
from zksync_sdk import ZkSyncLibrary

app = create_app()
babel = Babel(app) #language support
lib = ZkSyncLibrary()

@babel.localeselector
def get_locale():
    if current_user.is_authenticated:
        return current_user.user_lang or 'en'
    else:
        if session.get('userlang'):
            lng = session.get('userlang') or 'en'
        else:
            lng = request.accept_languages.best_match(app.config['LANGUAGES'].keys())
            session['userlang'] = lng
        return lng

@app.route('/')
@app.route('/home')
def home():
    try:
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.dashboard'))

        langs = []
        for lng in app.config['LANGUAGES'].items(): # items gives both: app.config['LANGUAGES'].keys() and .values()
            langs.append(lng)
        session['langs'] = langs        
        return render_template('index.html') 
    except Exception as e:
        app.logger.error(str(e), extra={'user': ''})
        return redirect(url_for('errors.error'))

@app.route('/setlanguage/<selectedLocale>')
def setlanguage(selectedLocale):
    session['userlang'] = selectedLocale
    return render_template('index.html')
