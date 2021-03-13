from eth_wallet import Wallet
from eth_wallet.utils import generate_entropy
from lynx.wallet.models import SavingsData
from lynx.dashboard.models import UserTransaction
import json
import requests
from web3 import Web3
from decimal import Decimal
import os
import datetime
from flask import current_app as app
import math
from lynx.wallet.helper import *
from lynx.wallet.savings import Savings


class SavingsCompound(Savings):

    def getDepositData(self):
        cdata = SavingsData
        cdata.current_balance = 0
        cdata.interest_accrued = 0
        cdata.ctoken_balance = 0
        symbol = 'c' + self.tokenSymbol.upper()

        w3 = getW3()
        contract_address = getTokenAddress(symbol)
        abi_json = getContractAbiJson('COMP')
        abi = abi_json[symbol]
        compound_token_contract = getContract(w3, abi, contract_address)

        user_underlyingbalance = compound_token_contract.functions.balanceOfUnderlying(
            self.userWallet.address).call()

        # underlying symbol (not compound symbol)
        cdata.symbol = symbol.replace('c', '', 1)
        cdata.current_balance = convertAmountFromWei(
            cdata.symbol, user_underlyingbalance)
        cdata.interest_accrued = 0

        return cdata

    # Using etherscan API to get user transactions
    def getUserTransactions(self):
        addr = self.userWallet.address.lower()
        if app.config['NET'] == 'mainnet':
            apiEndPoint = 'https://api.etherscan.io/api?module=account&action=tokentx&address=' + \
                addr + '&startblock=0&endblock=999999999&sort=asc&apikey=' + \
                app.config['ETHSCANM']
        elif app.config['NET'] == 'kovan':
            apiEndPoint = 'https://api-kovan.etherscan.io/api?module=account&action=tokentx&address=' + \
                addr + '&startblock=0&endblock=999999999&sort=asc&apikey=' + \
                app.config['ETHSCANR']
        else:
            apiEndPoint = 'https://api-ropsten.etherscan.io/api?module=account&action=tokentx&address=' + \
                addr + '&startblock=0&endblock=999999999&sort=asc&apikey=' + \
                app.config['ETHSCANR']

        headers = {
            'User-Agent': 'chrome'
        }
        # headers required for ropsten as it fails !!!
        trans = requests.get(apiEndPoint, headers=headers)
        jsonData = trans.json()

        transactionList = []
        compTokenContract = getTokenAddress('c' + self.tokenSymbol).lower()

        for transaction in jsonData['result']:
            # or transaction['tokenSymbol'] == 'c' + self.tokenSymbol:
            if transaction['tokenSymbol'] == self.tokenSymbol:
                userTran = UserTransaction()
                show = False

                # from user to contract
                if transaction['from'].lower() == addr.lower() and transaction['to'].lower() == compTokenContract:
                    userTran.transactionType = "Deposit"
                    show = True
                # from contract to user
                elif transaction['from'].lower() == compTokenContract and transaction['to'].lower() == addr:
                    userTran.transactionType = "Withdraw"
                    show = True

                if show == True:
                    ts = transaction['timeStamp']
                    userTran.transactionDate = str(
                        datetime.datetime.utcfromtimestamp(int(ts))) + ' UTC'
                    tokenDecimal = transaction['tokenDecimal']
                    amt = Decimal(transaction['value']) / \
                        10 ** Decimal(tokenDecimal)
                    userTran.transactionAmt = str(round(amt, 2))
                    transactionList.append(userTran)

        return transactionList

    # Deposit/mint to Compound
    def doDeposit(self, amt):
        w3 = getW3()
        contract_address = getTokenAddress('c' + self.tokenSymbol)
        abi_json = getContractAbiJson('COMP')
        abi = abi_json['c' + self.tokenSymbol]
        compound_token_contract = getContract(w3, abi, contract_address)
        nonce = w3.eth.getTransactionCount(self.userWallet.address)

        # convert in underlying token balance (USDT and not cUSDT)
        amount = convertAmountToWei(self.tokenSymbol, amt)
        mint_tx = compound_token_contract.functions.mint(int(amount)).buildTransaction({
            'chainId': getChainId(),  # 1 for mainnet, 3 for ropsten
            'gas': 220920,
            'gasPrice': w3.toWei(150, 'gwei'),
            'nonce': nonce
        })
        signed_txn = w3.eth.account.sign_transaction(
            mint_tx, self.userWallet.privateKey)
        try:
            tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
            return tx.hex()
        except ValueError as err:
            # return (json.loads(str(err).replace("'", '"')), 402, {'Content-Type': 'application/json'})
            return 'Error: ' + str(err)

    # Withdraw/redeem from Compound
    def doWithdraw(self, amt):
        w3 = getW3()
        contract_address = getTokenAddress('c' + self.tokenSymbol)
        abi_json = getContractAbiJson('COMP')
        abi = abi_json['c' + self.tokenSymbol]
        compound_token_contract = getContract(w3, abi, contract_address)
        nonce = w3.eth.getTransactionCount(self.userWallet.address)

        amount = convertAmountToWei(self.tokenSymbol, amt)
        redeem_tx = compound_token_contract.functions.redeemUnderlying(int(amount)).buildTransaction({
            'chainId': getChainId(),  # 1 for mainnet, 3 for ropsten
            'gas': 220920,
            'gasPrice': w3.toWei(150, 'gwei'),
            'nonce': nonce
        })

        signed_txn = w3.eth.account.sign_transaction(
            redeem_tx, self.userWallet.privateKey)
        try:
            tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
            return tx.hex()
        except ValueError as err:
            # return (json.loads(str(err).replace("'", '"')), 402, {'Content-Type': 'application/json'})
            return 'Error: ' + str(err)

    # Compound APY
    def getTokenAPY(self):
        symbol = 'c' + self.tokenSymbol.upper()
        w3 = getW3()
        contract_address = getTokenAddress(symbol)
        abi_json = getContractAbiJson('COMP')
        abi = abi_json[symbol]
        compound_token_contract = getContract(w3, abi, contract_address)

        Rate = compound_token_contract.functions.supplyRatePerBlock().call()
        ETH_Mantissa = 1 * 10 ** 18  # (ETH has 18 decimal places)
        # (based on 4 blocks occurring every minute)
        BlocksPerDay = 4 * 60 * 24
        DaysPerYear = 365

        # not same as compound website formula!!!
        APY = (((Rate / ETH_Mantissa * BlocksPerDay + 1) ** DaysPerYear) - 1) * 100
        #APY = (((math.pow((Rate / ETH_Mantissa * BlocksPerDay) + 1, DaysPerYear - 1))) - 1) * 100
        return APY
