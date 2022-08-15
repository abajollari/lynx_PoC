from flask import render_template, redirect, url_for, request, flash
from lynx.dashboard import bpDasboard
import datetime
from flask_login import login_required, current_user
from flask import current_app as app
from lynx.dashboard.models import Dashboard
from lynx.wallet.wallet import getWalletTokenBalance, getEthBalance, getGasPrice
from lynx.wallet.compound import SavingsCompound
from lynx.auth.models import User, UserWallet
from lynx.wallet.aave import SavingsAave


@bpDasboard.route('/dashboard')
@login_required
def dashboard():
    try:

        showWalletInfo = request.args.get('show') or ''

        erc20_symbol = app.config['SYMB']
        wall = UserWallet.query.filter_by(uid=current_user.id).first()
        savingPlatform = app.config['PROTOCOL']  # Compound / Aave

        # need some class factory to remove if/else
        if savingPlatform == 'COMP':
            compSavings = SavingsCompound(wall, erc20_symbol)
            dashboard_data = compSavings.getDepositData()
            trans_data = compSavings.getUserTransactions()
            dashboard_data.apy = str(round(compSavings.getTokenAPY(), 2))
        else:  # Aave
            aaveSavings = SavingsAave(wall, erc20_symbol)
            dashboard_data = aaveSavings.getDepositData()
            trans_data = aaveSavings.getUserTransactions()
            dashboard_data.apy = str(round(aaveSavings.getTokenAPY(), 2))

        erc20_balance = ''
        ethBalance = ''
        avg_gp = 0
        if showWalletInfo.upper() == 'Y':
            avg_gp = str(getGasPrice()*21000/1000000000)  + ' ETH' # gas 21000
            erc20_balance = str(getWalletTokenBalance(
                wall.address, erc20_symbol)) + ' ' + erc20_symbol
            ethBalance = str(getEthBalance(wall.address)) + ' ETH'

        return render_template('dashboard/dashboard.html', data=dashboard_data, transactionList=trans_data,
                               ad=wall.address, tokenbalance=erc20_balance, ethbalance=ethBalance, gasPrice=avg_gp,
                               showAddr=showWalletInfo.upper())
    except Exception as e:
        app.logger.error(str(e), extra={'user': ''})
        return redirect(url_for('errors.error'))
