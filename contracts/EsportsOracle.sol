// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract EsportsOracle {
    event MarketCreated(uint256 indexed id, bytes32 indexed eventId, string eventName, uint256 endTime, address creator);
    event MarketResolved(uint256 indexed id, bool outcome, address resolver, uint256 resolvedAt);

    struct Market {
        bytes32 eventId;
        string eventName;
        uint256 endTime;
        bool resolved;
        bool outcome;
        address creator;
        uint256 createdAt;
        uint256 resolvedAt;
    }

    address public owner;
    address public resolver;
    uint256 public marketCount;
    mapping(uint256 => Market) public markets;
    mapping(bytes32 => uint256) public marketIdByEventId; // 0 means none

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    modifier onlyResolver() {
        require(msg.sender == resolver || msg.sender == owner, "Not resolver");
        _;
    }

    constructor() {
        owner = msg.sender;
        resolver = msg.sender;
    }

    function setResolver(address _resolver) external onlyOwner {
        require(_resolver != address(0), "Resolver zero");
        resolver = _resolver;
    }

    function createMarket(bytes32 eventId, string memory eventName, uint256 endTime) external returns (uint256) {
        require(eventId != bytes32(0), "Invalid eventId");
        require(marketIdByEventId[eventId] == 0, "Market exists");
        marketCount += 1;
        uint256 id = marketCount;

        markets[id] = Market({
            eventId: eventId,
            eventName: eventName,
            endTime: endTime,
            resolved: false,
            outcome: false,
            creator: msg.sender,
            createdAt: block.timestamp,
            resolvedAt: 0
        });

        marketIdByEventId[eventId] = id;

        emit MarketCreated(id, eventId, eventName, endTime, msg.sender);
        return id;
    }

    function resolveMarket(uint256 id, bool outcome) external onlyResolver {
        Market storage m = markets[id];
        require(m.eventId != bytes32(0), "Market not found");
        require(!m.resolved, "Already resolved");
        // For hackathon speed: allow resolving any time
        m.resolved = true;
        m.outcome = outcome;
        m.resolvedAt = block.timestamp;

        emit MarketResolved(id, outcome, msg.sender, m.resolvedAt);
    }

    function getMarketByEvent(bytes32 eventId)
        external
        view
        returns (
            bool exists,
            uint256 id,
            bytes32 _eventId,
            string memory eventName,
            uint256 endTime,
            bool resolved,
            bool outcome,
            address creator,
            uint256 createdAt,
            uint256 resolvedAt
        )
    {
        id = marketIdByEventId[eventId];
        exists = (id != 0);
        if (!exists) {
            return (false, 0, bytes32(0), "", 0, false, false, address(0), 0, 0);
        }
        Market memory m = markets[id];
        return (true, id, m.eventId, m.eventName, m.endTime, m.resolved, m.outcome, m.creator, m.createdAt, m.resolvedAt);
    }
}
