# Analysis of BANC Synapse Count Distribution

## Step 1 — Data Source
- **File Used:** `/home/surjit/Desktop/flywire/v1/research_data/raw/BANC_v888/connections_princeton.csv.gz`
- **Edges Column:** `syn_count` (aggregated by grouping `pre_root_id` and `post_root_id`)
- **Total Unique Edges:** 3,037,361

## Step 6 — Low-Weight Edge Analysis
- **syn_count == 1:** 0 edges (0.00%)
- **syn_count == 2:** 0 edges (0.00%)
- **syn_count == 3:** 965,976 edges (31.80%)
- **syn_count <= 5:** 1,849,628 edges (60.90%)
- **syn_count <= 10:** 2,544,409 edges (83.77%)

## Step 7 — Clamp Bias Analysis

In the Synapse Count Measurement Error model, the weight perturbation applies `new_weight = max(round(original + noise), 1)`. Because a Gaussian noise distribution is symmetric, edges should theoretically experience increases and decreases with equal probability.

However, the clamp at 1 creates an asymmetric floor effect for edges with low weights. If an edge has a weight of 1, any negative noise that would reduce the weight below 1 is artificially pulled back up to 1. 

Given that **0.00%** of edges have exactly 1 synapse in the BANC dataset, this floor effect applies to **virtually none** of the network.

- **Exposure to Clamping:** Since there are exactly 0 edges with 1 synapse, and the minimum synapse count observed is 3, the vast majority of the network is far away from the `max(1, ...)` floor. 
- **Negligibility:** The clamping effect is highly **negligible**. The proportional noise scale ($\sigma = 	ext{rate} 	imes w$) for an edge of weight 3 at an error rate of 0.20 (20%) yields $\sigma = 0.6$. The probability of drawing a noise value $\le -2.5$ (to drop a weight of 3 down to $0.5$ and round to 0) from $\mathcal{N}(0, 0.6)$ is extremely low ($pprox 0.000015$). Thus, even at the highest modeled error rate, the floor is rarely hit.
- **Bias on Total Synapses:** Because the edges do not hit the floor, the positive and negative noise will cancel out across the network. The `Total Synapses` metric will not experience any systemic mathematical bias due to clamping.
- **Influence on Weighted PageRank:** Weighted PageRank relies heavily on the distribution of weights. Since the clamping does not artificially inflate the low-end weights, the transition probabilities remain structurally unbiased.

## Step 8 — Scientific Interpretation

**If very few edges have syn_count = 1, would the clamp likely have negligible influence?**  
Yes. The data reveals that exactly 0 edges have a synapse count of 1 or 2. Since the weakest edges in the graph start at 3 synapses, they are safely distanced from the `max(1, ...)` threshold given the tested error rates (up to 20%). The symmetrical Gaussian noise is able to fully express its negative tail without being prematurely truncated.

## Final Conclusion

**Based on the actual BANC synapse-count distribution, is the current max(1, ...) clamp likely to have a negligible, moderate, or significant impact on the scientific conclusions of the Synapse Count Measurement experiment?**

The impact is **negligible**. 

The analysis demonstrates that 0 edges (0.00%) have exactly 1 synapse, and the minimum connection strength is 3. 
Because the proportional Gaussian noise limits large variance to large weights, and small weights only experience small variance, the weight of 3 acts as a sufficient buffer against the `max(1, ...)` clamp. As a result, the perturbation behaves as a true zero-mean process across the graph. Any observed changes in network statistics (such as PageRank) can be safely attributed to the effects of the measurement uncertainty itself, rather than an artifact of mathematical clipping.
