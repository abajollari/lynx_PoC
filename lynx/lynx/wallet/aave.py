#from eth_wallet import Wallet
#from eth_wallet.utils import generate_entropy
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
from lynx.wallet.wallet import approve, isApproved, getWalletTokenBalance
from lynx.wallet.savings import Savings


class SavingsAave(Savings):

    def getDepositData(self):
        cdata = SavingsData
        cdata.current_balance = 0
        cdata.interest_accrued = 0
        cdata.ctoken_balance = 0
        symbol = 'a' + self.tokenSymbol.upper()

        w3 = getW3()
        contract_address = getTokenAddress(symbol)
        abi_json = getContractAbiJson('ATOKEN')  # Aave token
        abi = abi_json  # ['result']
        aave_token_contract = getContract(w3, abi, contract_address)

        user_underlyingbalance = aave_token_contract.functions.balanceOf(
            self.userWallet.address).call()

        # underlying symbol (not aave symbol)
        cdata.symbol = symbol.replace('a', '', 1)
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
        compTokenContract = getTokenAddress('a' + self.tokenSymbol).lower()

        for transaction in jsonData['result']:
            # or transaction['tokenSymbol'] == 'c' + tokenSymbol:
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

    # Deposit to Aave - actions(deposit/withdraw...) are performed against LendingPool contract and not against aToken like compound
    def doDeposit(self, amt):

        lendingPoolCntrAdd = self.__getLendingPoolAddr()

        # convert in underlying token balance (USDT and not cUSDT)
        amt = convertAmountToWei(self.tokenSymbol, amt)

        if not isApproved(self.userWallet.address, self.tokenSymbol, lendingPoolCntrAdd, amt, ''):
            approve(self.userWallet.address, self.tokenSymbol,
                    lendingPoolCntrAdd, amt, self.userWallet.privateKey, '')

        w3 = getW3()
        # lendingpool contract address
        contract_address = lendingPoolCntrAdd
        abi_json = getContractAbiJson('AAVE')
        abi = abi_json['result']
        lendingPool_contract = getContract(w3, abi, contract_address)
        nonce = w3.eth.getTransactionCount(self.userWallet.address)

        tokenAddress = getTokenAddress(self.tokenSymbol)  # 'a' + symbol)
        
        mint_tx = lendingPool_contract.functions.deposit(Web3.toChecksumAddress(tokenAddress), int(amt),
                                                         Web3.toChecksumAddress(self.userWallet.address), int(0)).buildTransaction({
                                                             'chainId': getChainId(),
                                                             'gas': 220920,
                                                             'gasPrice': w3.toWei('150', 'gwei'),
                                                             'nonce': nonce
                                                         })
        signed_txn = w3.eth.account.sign_transaction(
            mint_tx, self.userWallet.privateKey)
        try:
            tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
            return tx.hex()
            # txn_receipt = w3.eth.waitForTransactionReceipt(tx)
            # return txn_receipt
        except ValueError as err:
            # return (json.loads(str(err).replace("'", '"')), 402, {'Content-Type': 'application/json'})
            return 'Error: ' + str(err)

    # Withdraw from Aave
    def doWithdraw(self, amt):
        # function withdraw(address asset, uint256 amt, address to)
        w3 = getW3()
        # lendingpool contract address
        contract_address = self.__getLendingPoolAddr()
        abi_json = getContractAbiJson('AAVE')
        abi = abi_json['result']
        lendingPool_contract = getContract(w3, abi, contract_address)
        nonce = w3.eth.getTransactionCount(self.userWallet.address)

        tokenAddress = getTokenAddress(self.tokenSymbol)
        amt = convertAmountToWei(self.tokenSymbol, amt)
        redeem_tx = lendingPool_contract.functions.withdraw(Web3.toChecksumAddress(tokenAddress),
                                                            int(amt), Web3.toChecksumAddress(self.userWallet.address)).buildTransaction({
                                                                'chainId': getChainId(),
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

    # Aave APY
    def getTokenAPY(self):
        w3 = getW3()
        # lendingpool contract address
        contract_address = self.__getLendingPoolAddr()  # self.LENDING_POOL_CONTRACT_ADDR
        abi_json = getContractAbiJson('AAVE')
        abi = abi_json['result']
        lendingPool_contract = getContract(w3, abi, contract_address)

        tokenAddress = getTokenAddress(self.tokenSymbol)

        reserveData = lendingPool_contract.functions.getReserveData(
            Web3.toChecksumAddress(tokenAddress)).call()
        # fourth element has the borrowRate in ray (27 digits )
        return (reserveData[3] / 10 ** 27) * 100  # convert to %

    def __getLendingPoolAddr(self):
        if app.config['NET'] == 'mainnet':
            return '0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9'
        else:
            return '0xE0fBa4Fc209b4948668006B2bE61711b7f465bAe'
