This is the most confusing part, but once you see it with numbers, it becomes obvious.

Let's assume a very small network.

## Original network

Suppose you have **100 edges (connections)**.

Each edge has **6 synapses on average**.

| Edge     | Synapses |
| -------- | -------: |
| Edge 1   |        6 |
| Edge 2   |        6 |
| ...      |      ... |
| Edge 100 |        6 |

So,

* **100 edges**
* **6 synapses per edge (average)**

Total synapses:

[
100 \times 6 = 600
]

So the original network has:

* **100 edges**
* **600 synapses**

---

## Now apply a 20% False Synapse error

Your algorithm says:

> Add **20% more edges**.

20% of 100 edges = **20 new edges**.

Now you have:

* Original edges = 100
* New false edges = 20

Total:

**120 edges**

So the **edge count increased by 20%**.

✅ This matches your second graph.

---

## But how many synapses do these new edges have?

Here's the important part.

Your algorithm **does not** create strong edges.

Instead it samples from the **weak-edge distribution**.

Suppose every new edge has **3 synapses**.

So the 20 new edges contribute:

[
20 \times 3 = 60 \text{ new synapses}
]

---

## Now calculate total synapses

Originally:

[
600
]

Added:

[
60
]

Total:

[
660
]

Now calculate the percentage increase:

[
\frac{660-600}{600}\times100
============================

10%
]

So the graph shows:

* **Edges:** +20%
* **Synapses:** +10%

This is exactly what your graphs show.

---

## Why doesn't it become +20% synapses?

Because the **new edges are weaker than the original edges**.

Think of it like this:

Original edge:

```text
Neuron A ─────────────► Neuron B

6 synapses
```

False edge:

```text
Neuron C ─────────────► Neuron D

3 synapses
```

The false edge counts as **one new edge**, but it contributes only **half as many synapses** as a typical original edge.

So adding 20% more edges **does not** add 20% more synapses.

---

## An analogy

Imagine a classroom.

Originally:

* 100 students
* Each student has **6 books**

Total books:

[
100 \times 6 = 600
]

Now 20 new students join.

But each new student brings only **3 books**.

New books:

[
20 \times 3 = 60
]

Total books:

[
600+60=660
]

Students increased by:

**20%**

Books increased by:

**10%**

Exactly the same thing happens in your graph.

---

## This is the one sentence to remember for your presentation

> **The false-synapse model adds 20% more connections (edges), but each new connection is intentionally weak, containing only about half the average number of synapses of an existing connection. Therefore, the edge count increases by 20%, while the total synapse count increases by only about 10%.**

This is scientifically correct **if your implementation samples the new edge weights from the weak-edge distribution (approximately 3 synapses on average versus about 6 for existing edges)**, which matches the implementation you've described earlier.
