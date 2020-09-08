# 1. PREPARE
import json
import web3

# PREINPUT START----------------------
CHAIN_NAME = 'mainnet' # https://github.com/ethereum/EIPs/blob/master/EIPS/eip-155.md#list-of-chain-ids
ETHER_PRICE = 407 # [$]
GAS = 100000 # for ether use 21000, for contract try 100000 (transfer().estimateGas not possible)
GAS_PRICE_GWEI = 90  # https://etherscan.io/gastracker
INFURA_TOKEN = 'YOUR_ID'
# PREINPUT END----------------------

ADDRESS_FROM = web3.Web3.toChecksumAddress(input('ADDRESS_FROM:'))
ADDRESS_TO = web3.Web3.toChecksumAddress(input('ADDRESS_TO:'))

chain_id =  {'mainnet': 1, 'rinkeby': 4}[CHAIN_NAME]
w3 = web3.Web3(web3.Web3.HTTPProvider(f'https://{CHAIN_NAME}.infura.io/v3/{INFURA_TOKEN}'))
# pprint(w3.eth.getBlock('latest'))

# RINKEBY COMPATIBILTY: # https://web3py.readthedocs.io/en/latest/middleware.html?highlight=proof%20of%20auth#geth-style-proof-of-authority
if CHAIN_NAME == 'rinkeby':
    from web3.middleware import geth_poa_middleware
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# https://web3py.readthedocs.io/en/stable/web3.eth.account.html#sign-a-contract-transaction
tx = {
    'chainId': chain_id,
    'gas': GAS, # https://web3py.readthedocs.io/en/stable/web3.eth.html#web3.eth.Eth.estimateGas
    'gasPrice': w3.toWei(GAS_PRICE_GWEI, 'gwei'),
    "nonce": w3.eth.getTransactionCount(ADDRESS_FROM), # https://etherscan.io/ + 1
}


#############################################
# 2.Option1 PREPARE_eth (only eth transfers)
tx_value = input('VALUE (or ALL) [ETH]:')

tx['from'] = ADDRESS_FROM
tx['to'] = ADDRESS_TO

assert tx['gas'] == 21000, 'overestimate (bad cleanout if ALL)'
balance_from = w3.eth.getBalance(tx['from'])
gas_cost=tx['gas'] * tx['gasPrice']
tx['value'] = balance_from - gas_cost if tx_value == 'ALL' else w3.toWei(tx_value, 'ether')
assert gas_cost + tx['value'] <= balance_from, f"{gas_cost+tx['value']}<={balance_from}"

print(f"tx_value: {w3.fromWei(tx['value'], 'ether') * ETHER_PRICE }$")
print(f"gas_cost_dollar: {w3.fromWei(gas_cost, 'ether') * ETHER_PRICE }$")
print('JSON_TX: (with/without indent)')
print(json.dumps(tx, sort_keys=True, indent=4))
print(json.dumps(tx, sort_keys=True))
# del tx


#############################################
# 2.Option2 PREPARE_erc20 (only erc20 transfers)
ERC20_VALUE = input('ERC20_VALUE (or ALL) [TOKENS]:')
CONTRACT_ADDRESS = web3.Web3.toChecksumAddress(input('CONTRACT_ADDRESS:')) # https://etherscan.io
CONTRACT_ABI = input('CONTRACT_ABI:') # like [{"constant":true,"inputs":[... eg https://etherscan.io/address/0xf629cbd94d3791c9250152bd8dfbdf380e2a3b9c#code
assert ERC20_VALUE == 'ALL' or float(ERC20_VALUE)
assert CONTRACT_ADDRESS and CONTRACT_ABI, 'empty input'

contract_address = web3.Web3.toChecksumAddress(CONTRACT_ADDRESS)
contract = w3.eth.contract(contract_address, abi=CONTRACT_ABI)

raw_balance_from = contract.functions.balanceOf(ADDRESS_FROM).call()
decimals = contract.functions.decimals().call()
raw_value_erc20 = raw_balance_from if ERC20_VALUE == 'ALL' else float(ERC20_VALUE) * 10 ** decimals
assert raw_value_erc20 <= raw_balance_from, f'{raw_value_erc20}<={raw_balance_from}'

gas_cost = GAS * w3.toWei(GAS_PRICE_GWEI, 'gwei')
balance_from = w3.eth.getBalance(ADDRESS_FROM)
assert gas_cost <= balance_from, f"{gas_cost}<={balance_from}, minimum balance required: {w3.fromWei(gas_cost, 'ether')} ether"

print(f"contract_name: {contract.functions.name().call()}")
print(f"tx_value_erc20: {raw_value_erc20 // (10 ** decimals )}")
print(f"gas_cost_dollar: {w3.fromWei(gas_cost, 'ether') * ETHER_PRICE }$")

tx = contract.functions.transfer(ADDRESS_TO, raw_value_erc20).buildTransaction(tx)
assert tx['value'] == 0 # no eth transfer
# print(contract.decode_function_input(tx['data']) # funcargs
print('JSON_TX:')
print(json.dumps(tx, sort_keys=True, indent=4))
print(json.dumps(tx, sort_keys=True))
del tx


#############################################
# 3. SIGN  [standalone via pyinstaller]
import json
from getpass import getpass
from pprint import pprint

import web3

JSON_TX = input('JSON_TX (or JSON_TX_FILEPATH):')
KEYSTORE_FILEPATH = input('KEYSTORE_FILEPATH (or empyt and private key next field):')
KEYSTORE_PASSWORD = getpass('KEYSTORE_PASSWORD:')
assert JSON_TX and (KEYSTORE_FILEPATH or KEYSTORE_PASSWORD), 'empty input'
w3_ = web3.Web3()

try:
    tx_tosign = json.loads(JSON_TX)
except:
    with open(JSON_TX) as f:
        tx_tosign = json.load(f)

try:
    with open(KEYSTORE_FILEPATH) as f:
        keystore = json.load(f)
        private_key = w3_.eth.account.decrypt(keystore, KEYSTORE_PASSWORD)
except:
    private_key = KEYSTORE_PASSWORD

account = w3_.eth.account.from_key(private_key)
del private_key
del KEYSTORE_PASSWORD

pprint(tx_tosign)
pprint(f"value: {w3_.fromWei(tx_tosign['value'], 'ether')} ether")
assert input('sign?[y]:').lower() in ['y',], 'aborted.'

signed_tx = account.sign_transaction(tx_tosign)
print(f'raw transaction: {signed_tx.rawTransaction.hex()}')


#############################################
# 4. PUBLISH
RAW_SIGNED_TX = input('RAW_SIGNED_TX [0x..]:')

# sig = w3.toBytes(hexstr=RAW_SIGNED_TX) # hex_signature
# ec_recover_args = {'hex_message_hash': 'MISSING', 'v': w3.toInt(sig[-1]), 'hex_r': w3.toHex(sig[:32]), 'hex_s': w3.toHex(sig[32:64])} #  ecrecover sol func
# pprint(ec_recover_args)
assert input('send?[y]:').lower() in ['y',], 'aborted.'

tx_hash = w3.eth.sendRawTransaction(RAW_SIGNED_TX)
subdomain = f'{CHAIN_NAME}.' if CHAIN_NAME != 'mainnet' else ''
print(f'https://{subdomain}etherscan.io/tx/{tx_hash.hex()}')
print('Awaiting receipt:')
receipt = w3.eth.waitForTransactionReceipt(tx_hash, timeout=600, poll_latency=1)
pprint(receipt)