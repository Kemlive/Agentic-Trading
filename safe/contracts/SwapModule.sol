// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @dev Minimal Safe interface for module-executed calls.
interface ISafe {
    function execTransactionFromModule(address to, uint256 value, bytes calldata data, uint8 operation) external returns (bool success);
}

/// @title SwapModule — whitelist-guarded, capped swaps executed BY the Safe.
/// @notice The Safe owns the funds and executes the DEX swap (so proceeds return to the Safe).
///         A single delegate EOA may trigger swaps within per-token per-swap and daily caps,
///         restricted to whitelisted sell/buy tokens and one whitelisted router. Only the Safe
///         can configure it.
contract SwapModule {
    address public immutable safe;
    address public immutable router;

    address public delegate;

    struct Caps {
        uint256 perSwap;   // sell-token raw units per single swap
        uint256 daily;     // sell-token raw units per rolling 24h
        uint256 dayStart;
        uint256 spent;
    }

    mapping(address => bool) public allowedSell;
    mapping(address => bool) public allowedBuy;
    mapping(address => Caps) public caps; // per sell-token caps

    bytes4 internal constant SWAP_SELECTOR = bytes4(keccak256("swapExactTokensForTokens(uint256,uint256,(address,address,bool,address)[],address,uint256)"));
    bytes4 internal constant APPROVE_SELECTOR = bytes4(keccak256("approve(address,uint256)"));

    struct Route {
        address from;
        address to;
        bool stable;
        address factory;
    }

    event Swap(address indexed delegate, address indexed sellToken, address indexed buyToken, uint256 amountIn, uint256 minOut);
    event CapsSet(address indexed token, uint256 perSwap, uint256 daily);

    modifier onlySafe() { require(msg.sender == safe, "only safe"); _; }
    modifier onlyDelegate() { require(msg.sender == delegate, "only delegate"); _; }

    constructor(address _safe, address _router) {
        safe = _safe;
        router = _router;
    }

    /// @notice Set the delegate EOA.
    function setDelegate(address _delegate) external onlySafe {
        delegate = _delegate;
    }

    /// @notice Set per-sell-token caps (raw units). daily == 0 disables that token's trading.
    function setCaps(address token, uint256 perSwap, uint256 daily) external onlySafe {
        Caps storage c = caps[token];
        c.perSwap = perSwap;
        c.daily = daily;
        if (c.dayStart == 0) c.dayStart = block.timestamp;
        emit CapsSet(token, perSwap, daily);
    }

    /// @notice Allow/deny a token as sell and/or buy side.
    function setToken(address token, bool asSell, bool asBuy) external onlySafe {
        allowedSell[token] = asSell;
        allowedBuy[token] = asBuy;
    }

    /// @notice One-time: grant the router max allowance for a whitelisted sell token (Safe is spender).
    function approveRouter(address token) external onlySafe {
        require(allowedSell[token], "not allowlisted");
        bytes memory data = abi.encodeWithSelector(APPROVE_SELECTOR, router, type(uint256).max);
        require(ISafe(safe).execTransactionFromModule(token, 0, data, 0), "approve failed");
    }

    /// @notice Delegate-triggered swap. Proceeds are sent to the Safe (recipient == safe).
    function swap(
        address sellToken,
        address buyToken,
        uint256 amountIn,
        uint256 minOut,
        address poolFactory,
        bool stable,
        uint256 deadline
    ) external onlyDelegate {
        require(allowedSell[sellToken], "sell not allowed");
        require(allowedBuy[buyToken], "buy not allowed");

        Caps storage c = caps[sellToken];
        require(amountIn > 0 && amountIn <= c.perSwap, "per-swap cap");
        _rollDay(c);
        require(c.spent + amountIn <= c.daily, "daily cap");
        c.spent += amountIn;

        Route[] memory route = new Route[](1);
        route[0] = Route(sellToken, buyToken, stable, poolFactory);

        bytes memory data = abi.encodeWithSelector(SWAP_SELECTOR, amountIn, minOut, route, safe, deadline);
        require(ISafe(safe).execTransactionFromModule(router, 0, data, 0), "swap failed");

        emit Swap(delegate, sellToken, buyToken, amountIn, minOut);
    }

    function _rollDay(Caps storage c) internal {
        if (block.timestamp >= c.dayStart + 1 days) {
            c.dayStart = block.timestamp;
            c.spent = 0;
        }
    }
}

