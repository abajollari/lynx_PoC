from flask import current_app as app
from web3 import Web3
from lynx.wallet.helper import getChainId, convertAmountToWei, convertAmountFromWei, getTokenAddress, getW3, getContractAbiJson, getContract
from lynx.wallet.wallet import approve, isApproved, getWalletTokenBalance
import datetime
import time


class UniTrade():

    UNISWAP_CONTRACT_ADDR = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'

    def __init__(self, userWallet):
        self.userWallet = userWallet

    def tradeToken(self, token_symbol, token_amount):

        userToken = app.config['SYMB']  # token user owns

        availableBalance = getWalletTokenBalance(
            self.userWallet.address, userToken)
        if (availableBalance < token_amount):
            return "Insuficent amount in your wallet"

        uni_contract_address = self.UNISWAP_CONTRACT_ADDR
        # convert in underlying token balance
        amount = convertAmountToWei(userToken, token_amount)

        if not isApproved(self.userWallet.address, userToken, uni_contract_address, amount, 'UNI'):
            approve(self.userWallet.address, userToken,
                    uni_contract_address, amount, self.userWallet.privateKey, 'UNI')

        w3 = getW3()
        abi_json = getContractAbiJson('UNI')
        abi = abi_json['abi']
        uniswap_contract = getContract(w3, abi, uni_contract_address)
        nonce = w3.eth.getTransactionCount(self.userWallet.address)

    # function swapExactTokensForTokens
        # uint amountIn,
        # uint amountOutMin,
        # address[] calldata path,
        # address to,
        # uint deadline
        # ) external returns (uint[] memory amounts);

        # __convertAmountToWei('DAI', amt/2)
        amountOutMin = int(amount) * 0.0098
        addressPaths = [Web3.toChecksumAddress(getTokenAddress(
            userToken, 'UNI')), Web3.toChecksumAddress(getTokenAddress(token_symbol, 'UNI'))]

        # current_time = datetime.datetime.now(datetime.timezone.utc)
        # unix_timestamp = current_time.timestamp() # works if Python >= 3.3
        # deadline = int(unix_timestamp + (20 * 60)) # 20 minutes
        deadline = int(time.time()) + 10000

        trade_tx = uniswap_contract.functions.swapExactTokensForTokens(int(amount),
                                                                       int(amountOutMin),
                                                                       addressPaths,
                                                                       self.userWallet.address,
                                                                       deadline).buildTransaction({
                                                                           'chainId': getChainId(),
                                                                           'gas': 2209200,
                                                                           'gasPrice': w3.toWei(150, 'gwei'),
                                                                           'nonce': nonce
                                                                       })
        signed_txn = w3.eth.account.sign_transaction(
            trade_tx, self.userWallet.privateKey)
        try:
            tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
            # return tx.hex()
            try:
                txn_receipt = w3.eth.waitForTransactionReceipt(tx, timeout=300)
            except Exception:
                return {'status': 'failed', 'error': 'timeout'}
            else:
                return {'status': 'success', 'receipt': txn_receipt}

        except ValueError as err:
            # return (json.loads(str(err).replace("'", '"')), 402, {'Content-Type': 'application/json'})
            return 'Error: ' + str(err)

    def getAmountsOut(self, token_symbol, token_amount):

        # function getAmountsOut(uint amountIn, address[] memory path) internal view returns (uint[] memory amounts)
        userToken = app.config['SYMB']  # token user owns

        amount = convertAmountToWei(userToken, token_amount)

        w3 = getW3()
        abi_json = getContractAbiJson('UNI')
        abi = abi_json['abi']
        uniswap_contract = getContract(w3, abi, self.UNISWAP_CONTRACT_ADDR)

        addressPaths = [Web3.toChecksumAddress(getTokenAddress(userToken, 'UNI')),
                        Web3.toChecksumAddress(getTokenAddress('WETH', 'UNI')),
                        Web3.toChecksumAddress(getTokenAddress(token_symbol, 'UNI'))]

        amountsOut = uniswap_contract.functions.getAmountsOut(
            int(amount), addressPaths).call()

        return convertAmountFromWei(token_symbol, amountsOut[2])
