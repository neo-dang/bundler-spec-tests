import re

import pytest
from web3 import constants
import jsonrpcclient
from tests.utils import deploy_contract, deploy_wallet_contract, UserOperation, RPCRequest, assertRpcError, \
    CommandLineArgs, get_contract
from tests.types import RPCErrorCode


fast=False

ADDRESS_ZERO = constants.ADDRESS_ZERO

ruletable = '''
|                 | unstaked    | unstaked | staked  | staked  | st-throttled | st-throttled |
| --------------- | ----------- | -------- | ------- | ------- | ------------ | ------------ |
| rules           | **1st sim** | **2nd**  | **1st** | **2nd** | **1st**      | **2nd**      |
| No-storage      | ok          | ok       | ok      | ok      | throttle     | throttle     |
| Acct-ref-noinit | ok          | ok       | ok      | ok      | throttle     | throttle     |
| Acct-ref-init   | drop        | drop     | ok      | ok      | throttle     | throttle     |
| Acct-storage    | ok          | ok       | ok      | ok      | throttle     | throttle     |
| ent-storage     | drop        | drop     | ok      | ok      | throttle     | throttle     |
| ent-ref         | drop        | drop     | ok      | ok      | throttle     | throttle     |
| ent==sender     | 4           | 1        | ok      | ok      | throttle     | throttle     |
'''

# see actions in https://docs.google.com/document/d/1DFX5hUhv_fwqC7wez6SBT3pWTGfSDiV45NyXllhxYik/edit?usp=sharing
ok = 'ok'
throttle = 1
drop = 'drop'

# keys are rules to pass to our entity
# values are 6 columns: 2 columns for each scenario of (unstaked, staked, staked+throttle)
# the 2 are rule for 1st simulation (rpc/p2p) and rule for 2nd simulation (bundling)
rules = dict(
    no_storage=[ok, ok, ok, ok, throttle, throttle],
    # TODO: fail. acct_ref_noinit=[ok, ok, ok, ok, throttle, throttle],
    # TODO: fail. acct_ref_init=[drop, drop, ok, ok, throttle, throttle],
    acct_storage=[ok, ok, ok, ok, throttle, throttle],
    ent_storage=[drop, drop, ok, ok, throttle, throttle],
    ent_ref=[drop, drop, ok, ok, throttle, throttle],
    context=[drop, drop, ok, ok, throttle, throttle],

    # not a real rule: sender is entity just like others.
    # entSender=[4, 1, ok, ok, throttle, throttle],
)


rules_unstaked_drop = [ 'ent_storage', 'ent_ref']
rules_unstaked_ok = ['no_storage', 'acct_storage', 'acct_ref']

def setThrottled(ent):
    # todo: set proper values that will consider it "throttled"
    RPCRequest(method='aa_setReputation', params=[{
        'reputation': {
            ent.address: {
                'opsSeen': 1,
                'opsIncluded': 2
            }
        }
    }]).send().result


@pytest.fixture
def paymaster(w3, entrypoint_contract):
    return deploy_contract(w3, 'TestRulePaymaster', [entrypoint_contract.address], value=10 ** 18)

#send a userOp. raise exception with message and code from jsonrpc
def send(**kw):
    ret = UserOperation(**kw).send()
    if isinstance(ret, jsonrpcclient.Ok):
        return ret.result
    raise Exception('code=%s %s' % (ret.code, ret.message))

#add stake for entity. must implement "addStake(entryPoint, unstakeDelay) payable"
def addStake(w3, entryPoint, entity):
    rootAccount=w3.eth.accounts[0]
    entity.functions.addStake(entryPoint.address, 2).transact({'from': rootAccount, 'value': 3 ** 18})

#make a view call to initCode to extract "sender" address
# todo: remove helper (currently, python doesn't return excption "return data", so we do without the helper)
def getSenderAddress(entryPoint, helper, initCode):
    return helper.functions.getSenderAddress(entryPoint.address, initCode).call({'gas': 10000000})


@pytest.mark.parametrize('rule', rules.keys())
@pytest.mark.skipif('fast')
def test_paymaster_staked_ok(w3, entrypoint_contract, clearState, paymaster, two_wallets, rule):
    addStake(w3, entrypoint_contract, paymaster)
    senders = two_wallets
    for sender in senders:
        send(sender=sender, paymasterAndData=paymaster.address + rule.encode().hex())

@pytest.mark.skipif('fast')
@pytest.mark.parametrize('rule', rules_unstaked_ok)
def test_paymaster_unstaked_ok(w3, entrypoint_contract, clearState, paymaster, two_wallets, rule):
    senders = two_wallets
    for sender in senders:
        send(sender=sender, paymasterAndData=paymaster.address + rule.encode().hex())

@pytest.mark.skipif('fast')
@pytest.mark.parametrize('rule', rules_unstaked_drop + ['context'])
def test_paymaster_unstaked_drop(w3, entrypoint_contract, clearState, paymaster, two_wallets, rule):
    senders = two_wallets
    with pytest.raises(Exception, match='unstaked paymaster'):
        send(sender=senders[0], paymasterAndData=paymaster.address + rule.encode().hex())

def test_paymaster_unstaked_init_drop(w3, entrypoint_contract, helper, clearState, paymaster, two_wallets):
    rule='acct_ref'
    factory = deploy_contract(w3, 'TestRuleFactory', [entrypoint_contract.address])
    initCode = factory.address + factory.functions.create(123, '').build_transaction()['data'][2:]

    sender = getSenderAddress(entrypoint_contract, helper, initCode)

    paymasterAndData = paymaster.address + rule.encode().hex()
    with pytest.raises(Exception, match='paymaster has forbidden read'):
        send(sender=sender, initCode=initCode, verificationGasLimit=hex(10000000), paymasterAndData=paymasterAndData)

# return staticly-deployed two funded wallets
@pytest.fixture(scope='session')
def two_wallets(w3):
    return [
        deploy_wallet_contract(w3).address,
        deploy_wallet_contract(w3).address
    ]

@pytest.fixture
def helper(w3):
    return deploy_contract(w3, 'Helper')
