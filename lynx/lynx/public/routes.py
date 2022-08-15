from flask import render_template, redirect, url_for, request, flash
from lynx.public import bp
from lynx.public.forms import ContactForm
from lynx.services.mail_api import send_email
from flask import current_app as app


@bp.route('/about')
def about():
    return render_template('public/about.html')

@bp.route('/terms')
def terms():
    return render_template('public/terms.html')
    
@bp.route('/contact', methods=('GET', 'POST'))
def contact():
    form = ContactForm(request.form)
    if request.method == "POST":
        if form.validate() == False:    
            return render_template('public/contact.html',form = form)
            
        inputMessage = form.inputMessage.data
        inputName = form.inputName.data
        inputEmail = form.inputEmail.data

        send_email('LynX - Contact Request', app.config['ADMINS'],
        'Name: ' + inputName + '\n' + 'Email: ' + inputEmail +  '\n\n' + 'Message: ' + inputMessage, '')

        flash("Thank You. Your request has been received. We will respond to you as soon as possible.")
        return redirect("/") #go to home page

    return render_template('public/contact.html',form = form)

@bp.route('/save')
def save():
    return render_template('public/save.html')

@bp.route('/invest')
def invest():
    return render_template('public/invest.html')

@bp.route('/send')
def send():
    return render_template('public/send.html')

