# Algorithm Report: Min-Cost Flow for Leakage Localization

## 1. Problem Statement
The Machine Learning layer is adept at flagging that an anomaly occurred on a specific route during a specific hour. However, a transit route may consist of 40+ stops. Sending an inspector to ride the entire route is inefficient. The problem is to localize the exact segment (Stop A to Stop B) where the revenue leakage occurred.

## 2. Graph Formulation
We model the transit route as a **Time-Expanded Flow Network**.
*   **Nodes**: Represent a specific bus stop at a specific time window.
*   **Edges**: Represent the physical segment between two sequential stops. 
*   **Capacity**: The maximum physical capacity of the bus.
*   **Cost**: The cost of an edge is formulated as the *inverse of the revenue discrepancy*. If a segment has a massive gap between expected revenue and reported revenue, the "cost" of pushing flow through that segment is drastically reduced.

## 3. Min-Cost Max-Flow Execution
The algorithm attempts to push a unit of "investigation flow" from the route's start node to its end node. 
Because the algorithm seeks the path of *minimum cost*, and cost is inversely proportional to the revenue discrepancy, the flow naturally routes itself through the segments with the highest revenue leakage.

## 4. Shortest Path Faster Algorithm (SPFA)
To solve the Min-Cost Flow problem efficiently, we implement SPFA.
*   **Why SPFA?**: Traditional Dijkstra's algorithm cannot handle negative edge costs (which can arise in specific discrepancy formulations). Bellman-Ford can handle negative edges but is slow O(V*E). SPFA improves upon Bellman-Ford using a queue-based relaxation technique, offering an average-case time complexity of O(E).
*   **Complexity**: 
    *   Time Complexity: Average O(E), Worst-case O(V*E)
    *   Space Complexity: O(V) for the queue and distance arrays.
*   **Result**: The edges that receive the flow are extracted and ranked. These segments represent the localized physical locations of the fare evasion or revenue leakage.

## 5. Implementation Details
The algorithm is implemented from scratch in pure JavaScript in `algorithm-layer/flow-localization.js`. It does not rely on heavy external graph libraries, ensuring it remains lightweight and executable in standard Node.js serverless environments.
