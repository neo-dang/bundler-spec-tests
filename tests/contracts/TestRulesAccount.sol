// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.15;

import "@account-abstraction/contracts/interfaces/IAccount.sol";
import "./OpcodeRules.sol";

contract TestRulesAccount is IAccount {

    using OpcodeRules for string;

    uint public state;
    TestCoin public coin;

    event State(uint oldState, uint newState);

    constructor(address _ep) payable {
        if (_ep != address(0)) {
            (bool req,) = address(_ep).call{value : msg.value}("");
            require(req);
        }
        //TODO: setCoin from constructor means we can't create this coin from initCode...
        setCoin(new TestCoin());
    }

    function setState(uint _state) external {
        emit State(state, _state);
        state = _state;
    }

    function setCoin(TestCoin _coin) public returns (uint){
        coin = _coin;
        return 0;
    }

    function eq(string memory a, string memory b) internal pure returns (bool) {
        return keccak256(bytes(a)) == keccak256(bytes(b));
    }

    function validateUserOp(UserOperation calldata userOp, bytes32, address, uint256 missingAccountFunds)
    external override returns (uint256 deadline) {
        if (missingAccountFunds > 0) {
            /* solhint-disable-next-line avoid-low-level-calls */
            (bool success,) = msg.sender.call{value : missingAccountFunds}("");
            success;
        }
        string memory rule = string(userOp.signature);
        require(OpcodeRules.runRule(rule, coin) != OpcodeRules.UNKNOWN, string.concat("unknown rule: ", rule));
        return 0;
    }
}
