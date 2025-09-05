# Pàgina 1

A Deep Dive into 3D Physics Engines for
Automotive Part Packaging in Python
This report provides a comprehensive analysis of open-source physics engines and related libraries
suitable for developing an automotive part packaging assistant in Python. The focus is on engines
capable of handling static packaging validation, spatial arrangement, collision detection, and
rotational transformations for 3D boxes. The analysis covers the technical features of available
engines, integration strategies with visualization tools, implementation challenges, and strategic
recommendations for building a robust and efficient system. The insights are derived exclusively
from the provided source materials to ensure factual accuracy and fidelity.
Comparative Analysis of Open-Source 3D Physics Engines
Selecting the right physics engine is the foundational decision for any packaging simulation project.
For an automotive parts application requiring static validation and spatial arrangement, the choice
must balance computational efficiency, algorithmic sophistication, feature set, and ease of
integration. Several prominent open-source engines offer capabilities relevant to this task, each with
distinct architectural philosophies and strengths. The primary candidates based on the provided
context are PyBullet, ReactPhysics3D, Project Chrono, and Coal.
PyBullet, a Python port of the Bullet Physics SDK, stands out as one of the most accessible options
due to its native Python support 
. It is designed for real-time collision detection and multi-physics
simulation, making it popular in robotics and game development 
. Its core strength lies in
providing a comprehensive API for rigid body dynamics, including gravity, forces, joints, and
frictional contacts 
. For the user's requirements, PyBullet directly supports Oriented Bounding
Box (OBB) collision detection for boxes and manages rotation through its internal 
btQuaternion representation, which inherently avoids gimbal lock 
. This makes it a
powerful tool for simulating realistic physical interactions. However, its primary design is for
dynamic, real-time simulations, which may be overkill for a static validation tool where performance
can be optimized by focusing only on the final arrangement state. Furthermore, while it can run in
"DIRECT" mode for headless operation, ensuring deterministic results across different hardware
remains a known challenge 
.
ReactPhysics3D is a C++ engine with Python bindings that offers a compelling alternative 
.
Released under the permissive ZLib license, it is highly regarded for its clean architecture and
performance 
. Like PyBullet, it supports OBBs for precise collision detection using the Separating
Axis Theorem (SAT) and Gilbert-Johnson-Keerthi (GJK) algorithms 
. Its key advantage is a
strong emphasis on precision and stability. It includes features like configurable solver iterations (10
for velocity, 5 for position by default), sleep thresholds to stabilize static arrangements, and a debug
renderer for visualizing contact points and normals 
. Because it is deterministic on the same
machine when recreated in the same order, it is well-suited for applications where consistent results
are critical, such as quality control in manufacturing 
. While it requires integration via bindings, its
3
3
25
1
3
3
47
34 35
3
33
30
30 41
30
30


# Pàgina 2

stable API and lack of external dependencies make it a robust choice for a production environment 
.
Project Chrono is another mature, open-source library released under a BSD-3 license, offering
extensive capabilities for engineering-level simulations 
. It is written in C++ but has a dedicated
Python interface, making it a viable option 
. Chrono excels at modeling complex mechanical
systems, supporting not just rigid bodies but also joints with limited rotations, actuators, springs, and
more 
. Its non-smooth dynamics time integration is particularly noted for being robust in handling
contact simulations 
. For the packaging problem, these advanced joint and constraint features
could be leveraged to model fixtures or assembly constraints between parts. Chrono also integrates
well with other scientific Python libraries like NumPy and TensorFlow, which could be beneficial if
the packaging assistant needs to incorporate AI-driven optimization layers 
. However, its feature
set is broader than strictly necessary for simple static packing, which might introduce unnecessary
complexity and overhead.
Coal represents a more specialized but highly performant option. As a high-performance collision
detection library derived from FCL, it provides Python bindings and is explicitly designed for speed 
. In benchmarks, it has been shown to outperform Bullet and FCL by up to 15 times 
. It
implements the GJK and Expanding Polytope Algorithm (EPA) for collision detection and distance
computation, which are industry-standard, precise methods 
. Unlike the others, Coal does not
provide a full physics simulation; it is purely a collision detection library. This makes it an ideal
candidate for a "physics-validation" backend where you need extremely fast and accurate collision
checks, potentially paired with a simpler geometric arrangement algorithm. Its use of
Boost.Serialization for serialization also suggests a high degree of maturity and flexibility 
.
The following table summarizes the key characteristics of these leading engines:
Feature /
Engine
PyBullet
ReactPhysics3D
Project
Chrono
Coal
Primary
Language
Python/C++ 
C++ 
C++ 
Python/C++ 
Python
Bindings
Native 
Implied via language
support 
Yes 
Yes 
License
Unknown (part of
Bullet SDK) 
ZLib 
BSD-3-Clause 
Unknown
(part of FCL) 
Collision
Shapes
OBB, AABB, Sphere,
Capsule, etc. 
Box, Sphere,
Capsule, Convex
Mesh, etc. 
Rigid Body
Dynamics,
Joints, etc. 
OBB, AABB,
Box, Capsule,
etc. 
Collision
Detection
GJK/EPA, SAT 
GJK/SAT 
Non-smooth
dynamics time
integrator 
GJK/EPA 
32
1
1
1
1
1
23
23
23
23
3
33
3
23
3
3
1
23
3
30
1
23
3
30 32
1
23
25 38
30 41
1
23


# Pàgina 3

Feature /
Engine
PyBullet
ReactPhysics3D
Project
Chrono
Coal
Rotation
Handling
btQuaternion,
avoids gimbal lock 
Built-in support via
math library 
General rigid
body dynamics 
Via math
library
operations
Static/
Dynamic
Focus
Real-time dynamic
simulation 
Static/dynamic
simulation 
Dynamic
simulation 
Static collision
queries
Integration
Complexity
Low (native Python) 
Moderate (requires
bindings) 
High (complex
feature set) 
Low
(specialized
library) 
Ultimately, for a static packaging assistant, ReactPhysics3D presents the most balanced profile: it is a
dedicated, stable, and precise physics engine with good Python integration and features perfectly
suited for validating static arrangements. PyBullet is a close second due to its accessibility, while Coal
is an excellent choice for a high-performance backend focused solely on collision checking.
Core Collision Detection and Rotational Transformation Concepts
Achieving accurate and reliable collision detection and rotational transformation is fundamental to
the success of a packaging assistant. These concepts move beyond simple bounding box intersection
tests and involve sophisticated mathematical principles to handle arbitrarily oriented 3D objects.
Understanding these principles is crucial for both selecting an appropriate engine and
troubleshooting potential issues.
At the heart of modern 3D collision detection are two main phases: broad-phase and narrow-phase.
The broad phase aims to quickly eliminate pairs of objects that cannot possibly be colliding, reducing
the number of expensive detailed checks. This is often achieved using Axis-Aligned Bounding Boxes
(AABBs)—boxes aligned with the coordinate axes—which are computationally cheap to test for
overlap 
. Spatial partitioning data structures like Dynamic AABB Trees or Octrees are used to
efficiently manage and query these bounding volumes 
. Once a pair of objects passes the broad-
phase test, the narrow-phase begins. This involves precise geometric tests to determine if the actual
shapes of the objects intersect. For convex polyhedra like boxes, the Separating Axis Theorem (SAT)
is a classic and effective method. To apply SAT, one must test a set of axes to see if there is a plane
(a separating axis) that can divide the two objects 
. If such an axis is found, the objects do not
collide. For two Oriented Bounding Boxes (OBBs), 15 potential separating axes must be tested,
which includes the three local face normals of each box and the nine axes formed from the cross
products of all pairs of face normals from both boxes 
. More general and numerically robust
algorithms like the Gilbert-Johnson-Keerthi (GJK) algorithm and its extension, the Expanding
Polytope Algorithm (EPA), are now standard in many professional engines 
. GJK works by
determining if the Minkowski difference of two shapes contains the origin, and EPA can then
compute the penetration depth and minimum translation vector (MTV) if a collision is detected 
.
47
43
1
3
30
1
3
33
1
23
15 46
38 41
43 45
43
12 38
38 41


# Pàgina 4

Handling rotation without introducing artifacts like gimbal lock is equally critical. Gimbal lock is a
phenomenon that occurs with Euler angles (rotations around X, Y, and Z axes) where two axes align
during certain rotations, causing a loss of a degree of freedom 
. To circumvent this, modern
engines and libraries universally use quaternions. A quaternion is a four-dimensional mathematical
entity represented as a vector (x, y, z) and a scalar (w) 
. It can represent a rotation as a single
operation around an arbitrary axis, avoiding the sequential-axis problems of Euler angles 
. Most
physics engines, including PyBullet (btQuaternion) and ReactPhysics3D, use quaternions
internally for representing and interpolating rotations 
. When integrating a physics engine with a
visualization library like Open3D or FURY, synchronizing the rotation is a common point of failure.
Quaternions from the physics engine must be correctly converted to a format the visualization library
understands, typically a 3x3 rotation matrix or Euler angles 
. Converting quaternions to Euler
angles can be problematic due to ambiguous solutions and "gimbal-like" behavior near singularities,
especially when trying to animate smooth transitions 
. Therefore, converting the quaternion to a
rotation matrix and applying that matrix directly to the object's transform is the recommended
approach 
. A specific issue noted was that some libraries (like Blender) apply relative rotations,
while others (like Open3D) expect world-space rotations, necessitating careful handling of
transformation composition 
.
The process of testing for collision between two rotated boxes involves transforming one object into
the local coordinate system of the other to simplify the calculations 
. By aligning one box with the
coordinate system, the problem reduces to testing if the other, transformed box penetrates its faces.
This is essentially what the SAT algorithm does implicitly by testing separation along the combined
axes. For visualization, once the physics engine computes the final resting positions and orientations
of all parts, these transforms must be accurately applied to the corresponding graphical models. Any
discrepancy, such as incorrect matrix multiplication or misinterpretation of the rotation convention
(e.g., PyBullet uses roll-pitch-yaw Euler angles 
), will result in a visually incorrect scene,
undermining the entire purpose of the packaging assistant 
.
Strategies for Visualization and Simulation Integration
A successful packaging assistant requires a tight coupling between the physics simulation, which
determines the feasibility of an arrangement, and the visualization, which presents this information to
the user. Integrating these two components in Python is a well-trodden path, with several established
frameworks and libraries available. The strategy chosen depends on the desired level of interactivity,
performance requirements, and existing skillset.
The most direct and commonly documented approach is to integrate a physics engine like PyBullet
with a scientific visualization library such as Mayavi or FURY. Mayavi is a powerful 3D scientific data
visualization toolkit built on VTK, offering interactive rendering with scriptable controls 
. FURY
(Functionally-sound, Interactive, and Rapid prototyping for You) is a higher-level Python library
built on VTK specifically for neuroimaging but is versatile enough for general 3D visualization 
.
The typical workflow involves running the physics simulation in a separate thread or stepping it
forward in small increments. After each step, the application retrieves the updated position and
orientation of each simulated object from the physics engine. These transforms are then applied to
the corresponding graphical actors in the visualization scene 
. This synchronization loop allows for
real-time visualization of dynamic simulations, such as dropping boxes onto a pallet, or for iteratively
2
47
2
43 47
39 49
44
39
42
2
48
28
14 20
34
34


# Pàgina 5

building a static arrangement by placing one box at a time and checking for collisions after each
placement 
. For instance, PyBullet can be run in "DIRECT" mode for headless simulation within a
Python script, while FURY manages the rendering window and updates the scene based on the data
from PyBullet 
.
For projects heavily invested in the Blender ecosystem, a natural integration path exists. Blender itself
has a built-in game engine logic that can perform collision detection, although this is less flexible
than a custom solution 
. A more robust approach would be to use the Kubric framework, which is
an open-source Python library designed to generate large-scale synthetic datasets with annotated 3D
scenes 
. Kubric interfaces with Blender and PyBullet, allowing for the creation of complex scenes
with physically plausible interactions that can then be rendered by Blender's powerful engine 
. This
is particularly useful for generating training data for machine learning models or for creating high-
quality visualizations of packaging scenarios.
For projects prioritizing performance and customizability, a lower-level integration with Open3D is
an excellent choice. Open3D is a modern, high-performance library for 3D data processing and
visualization with Python bindings 
. It provides a Visualizer class that enables non-
blocking, real-time updates to a 3D scene 
. The workflow here is similar to the PyBullet-FURY
approach: the physics simulation runs, and in a tight loop, the resulting transforms are applied to
Open3D geometry objects (like TriangleMesh instances representing the boxes). The 
vis.update_geometry() method is then called to refresh the object's position in the scene,
followed by vis.poll_events() and vis.update_renderer() to process GUI events
and render the new frame 
. Open3D excels at this kind of interactive visualization, offering
intuitive camera controls and the ability to capture images or depth buffers automatically for further
processing or rendering 
. A significant practical benefit is its ability to create wireframe
representations of boxes using LineSet, which is much faster to render than solid meshes,
allowing for smoother interaction when manipulating many parts 
.
Finally, for maximum flexibility, one can bypass the high-level wrappers and use the raw C++
libraries directly, interfacing them with Python via tools like pybind11. This is the route taken by 
JoltPhysics, a high-performance engine used in AAA games, which provides a JavaScript binding
(JoltPhysics.js) that could theoretically be adapted for Python 
. Similarly, ReactPhysics3D and
Project Chrono are C++ engines that could be wrapped with pybind11 
. This approach offers
maximum control and performance but comes at the cost of significantly increased development
complexity and maintenance burden. It should only be considered for projects with very specific
performance requirements that cannot be met by higher-level libraries.
Implementation Challenges and Best Practices
While the conceptual framework for a packaging assistant appears straightforward, its practical
implementation in Python reveals several nuanced challenges related to data synchronization,
numerical stability, and performance. Addressing these issues proactively is essential for building a
reliable and user-friendly tool.
One of the most frequent and difficult challenges is synchronizing the physics state with the
visualization. As discussed previously, this involves correctly converting and applying
transformations from the physics engine's coordinate system to the visualization library's coordinate
34
34
17
3
3
36 40
40
40
26 29
36
13
1
32


# Pàgina 6

system 
. A common pitfall arises when converting quaternions to Euler angles for use in
OpenGL-based renderers; this conversion can lead to unexpected "jumps" in angles and gimbal-like
locking behavior due to the ambiguity of inverse trigonometric functions and sign flips in the
underlying quaternion representation 
. The best practice is to avoid Euler angles entirely for this
conversion. Instead, convert the physics engine's quaternion to a 3x3 or 4x4 transformation matrix
and pass that directly to the visualization library 
. Furthermore, care must be taken with rotation
conventions. PyBullet, for example, uses a fixed-axis roll-pitch-yaw (X-Y-Z) order, which is
important to know when interpreting its output 
. Another subtle issue, highlighted in a GitHub
discussion, is the difference between relative and world-space rotations. Some libraries apply
transformations relative to the object's current orientation, while others apply them in the world
coordinate frame, which can lead to drastically different results if not handled correctly 
.
Ensuring numerical stability and determinism is another critical concern. In a static packaging
scenario, we want the simulation to reach a stable, unchanging state. However, physics engines use
iterative solvers to resolve simultaneous collisions, and these solvers have convergence criteria. If the
solver doesn't fully converge, objects may jitter or appear to slowly sink into each other, even when
they should be at rest 
. Many engines, including ReactPhysics3D and PyBullet, implement a
"sleeping" mechanism where objects with velocities below a certain threshold are suspended from
simulation to save computation and improve stability 
. Tuning the solver iteration counts and
sleep thresholds is a key part of calibrating the engine for a static validation task. Determinism—the
property that the simulation produces the exact same result given the exact same inputs on the same
machine—is also a challenge. Small differences in floating-point arithmetic across different hardware
can lead to slightly different simulation outcomes, which is unacceptable for a verification tool 
.
Engines like ReactPhysics3D are designed to be deterministic, but this must be managed carefully 
.
Performance optimization is paramount, especially when dealing with complex assemblies of many
parts. The primary bottleneck is often the narrow-phase collision detection. Efficient broad-phase
techniques, such as using Dynamic AABB Trees, are crucial for pruning the vast number of potential
collision pairs 
. Additionally, developers must consider how the packaging algorithm itself is
implemented. A brute-force approach that tries every possible permutation of part placements is
computationally intractable. More intelligent algorithms are required. One heuristic approach,
inspired by real-world logistics, is to sort items from largest to smallest and place each item in the
"best-fitting" available space 
. Alternatively, more advanced constructive heuristics or
metaheuristics like genetic algorithms or reinforcement learning can be employed 
. For example,
one paper details a method using acceleration forces to pack components, which proved effective for
complex geometries 
. The choice of algorithm will depend on the desired trade-off between speed
and optimality.
Finally, managing the transition from a dynamic simulation to a static arrangement requires careful
design. In a dynamic simulation, objects are constantly moving and interacting. For static validation,
we want to bring the system to a halt. Using kinematic bodies—objects that are moved by the user or
algorithm but still participate in collision detection—is a common technique. However, directly
setting their state using methods like setWorldTransform can sometimes cause instability 
. A
more robust method is to use interpolation (setInterpolationWorldTransform) or
specialized motion states that allow the physics engine to smoothly update the object's position
without causing disruptive impulses 
. By adopting these best practices, developers can navigate the
common pitfalls and build a robust and reliable packaging assistant.
28 34
44
39
48
42
46
30 46
35
30
33 38
8
4
6
12
35
35


# Pàgina 7

Advanced Techniques for Packing Optimization
Beyond basic collision detection, a truly powerful packaging assistant should incorporate advanced
algorithms to optimize the spatial arrangement of automotive parts. These techniques move from
simply verifying that a packing configuration is possible to finding the best possible configuration
according to a set of predefined objectives. The sources describe a spectrum of approaches, from
simple heuristics to complex, AI-driven methods.
One of the most intuitive and widely applicable techniques is the constructive heuristic. This
approach builds a solution incrementally. A classic example is the "First Fit Decreasing" (FFD)
algorithm, which first sorts the items to be packed by size (e.g., volume) in descending order 
. The
algorithm then takes each item in turn and places it in the first available container or location where
it fits without overlapping other items. A more sophisticated version, as described in a reference for
shipping, orders items from big to small and fits the biggest item into the smallest possible free space 
. This greedy approach is generally fast and provides reasonably good solutions for many practical
problems. The py3dbp library is a concrete implementation of such a constructive bin-packing
algorithm in Python, allowing for item rotation and returning computed positions and orientations
for 3D boxes 
.
For problems where the objective is to maximize the utilization of a finite space, such as fitting as
many parts as possible into a shipping container or optimizing the layout of components within an
engine bay, more advanced optimization techniques are required. Constrained Quadratic Models
(CQM) provide a formal way to encode such problems. A GitHub repository for a 3D bin packing
solver uses a CQM to minimize the number of bins and the overall packing height 
. The model
defines binary variables for each item-bin orientation combination and uses constraints encoded as
quadratic equations to enforce rules like "each item must be placed exactly once," "items cannot
overlap," and "must fit within bin boundaries" 
. This type of formulation can be solved using
various solvers, including quantum computing services like D-Wave's Leap platform, offering a novel
path to solving combinatorially hard problems 
.
Perhaps the most innovative and powerful approach detailed in the sources is the physics-based
optimization algorithm. This method treats the packing problem as a physical system to be
minimized in energy. In this paradigm, the automotive parts are modeled as rigid bodies within a
confined volume 
. An initial random arrangement is generated, likely with overlaps. The simulation
then proceeds by applying artificial "forces" to the parts: * Geometric Overlap Resolution (GOR): A
force that pushes overlapping parts apart along their penetration vectors. * Component Attraction
(CA): A weak attractive force between parts to encourage them to settle together and fill voids. * 
Domain Encapsulation (DE): A force that gently pulls parts towards a central region of the
container. * Rotational Inertia Reduction (RIR): A force that tends to align parts with the principal
axes of their inertia tensor, promoting stable, flat-on orientations 
. These forces are applied
alongside gravity and damping. The system is numerically integrated over time, and if configured
correctly, it will evolve from a chaotic, overlapping state to a stable, dense, and valid packing
arrangement. This approach has demonstrated impressive results, achieving packing densities of over
95% for cubes and tetracubes in simulation 
. A real-world application on a hybrid urban air
mobility nacelle showed high success rates, proving the concept's viability for complex industrial
geometries 
.
8
8
9
6
6
6
12
12
12
12


# Pàgina 8

Other techniques include dynamic-volume-based packing, which is particularly relevant for
deformable parts. This algorithm considers how items compress under their own weight, adjusting
their dimensions during the packing process to achieve a denser arrangement 
. For irregular items,
a bottom-left-fill strategy with multiple pivot points can be effective 
. Finally, for simpler, repetitive
tasks, a divide-and-conquer approach can be surprisingly effective. This involves breaking down a
large container into a grid of standardized sub-volumes (like pallets or fixed-size boxes), simplifying
the problem and avoiding the combinatorial explosion of trying to find a perfect fit for every
individual part 
. The choice of optimization technique ultimately depends on the specific problem
domain, the complexity of the parts, and the desired balance between computational speed and
solution quality.
Strategic Recommendations for Building a Robust System
Based on the comprehensive analysis of available engines, algorithms, and implementation
challenges, a clear strategic path emerges for developing a robust and efficient automotive part
packaging assistant in Python. The final recommendation hinges on balancing the need for precise
physics simulation with the goal of static, validated arrangements.
The recommended architecture for this project is a modular, two-tiered system. The core of the
system should be a dedicated physics engine responsible for all collision detection and stability
calculations. This engine should be complemented by a high-performance Python-based layer that
orchestrates the packing algorithm and serves as the bridge to the visualization frontend. This
separation of concerns ensures that the physics logic is encapsulated and can be validated
independently.
For the physics engine core, ReactPhysics3D stands out as the optimal choice. Its explicit design for
precision and stability, coupled with its deterministic nature on a single machine, makes it
exceptionally well-suited for a validation tool where consistent and repeatable results are paramount 
. Its Python bindings are a known and viable integration path 
, and its focus on rigid body
dynamics and OBB collision detection directly addresses the user's core requirements 
. While 
PyBullet is more accessible due to its native Python bindings, its primary identity as a real-time
simulation engine introduces complexities related to determinism and stability that would require
more effort to mitigate 
. Coal could serve as an excellent backend for a specialized collision-
checking module within this architecture, offering unparalleled speed for the narrow task of
validating whether a proposed arrangement is collision-free 
.
The packaging algorithm layer should be implemented in Python. This layer's responsibility is to
generate candidate arrangements for the physics engine to validate. For many practical applications,
starting with a constructive heuristic is the most pragmatic approach. An algorithm that sorts parts
by size and applies a "first-fit" or "best-fit" placement strategy is relatively simple to implement and
can produce excellent results for a wide range of scenarios 
. Libraries like py3dbp provide a
ready-made foundation for this approach 
. For more demanding optimization problems, this layer
can be extended to use more advanced techniques. A Constrained Quadratic Model (CQM) solver,
potentially interfaced with a quantum cloud service like D-Wave, can be used for highly constrained
optimization problems where maximizing space utilization is the sole goal 
. For complex, free-form
5
5
8
30 41
3
30
35
23
8
9
6


# Pàgina 9

arrangements, the physics-based optimization algorithm offers a powerful and elegant solution,
treating the packing problem as a natural physical process that converges to a stable, dense state 
.
The visualization frontend should leverage a high-performance library like Open3D. Open3D's 
Visualizer class is designed for the kind of real-time, non-blocking updates needed for an
interactive application 
. Its ability to efficiently render wireframe boxes with LineSet is
particularly advantageous for visualizing many parts without overwhelming the GPU 
. The
integration pattern is straightforward: the Python algorithm layer generates a proposed arrangement
(positions and orientations), sends it to the ReactPhysics3D engine for validation, and upon receiving
a positive result, instructs the Open3D visualizer to render the new state. This tight feedback loop
provides immediate visual confirmation to the user.
To summarize the final recommendation, the most robust and maintainable path forward is to: 1. 
Select ReactPhysics3D as the core physics engine for its precision, stability, and suitability for static
validation. 2. Develop the packing logic in Python, starting with a constructive heuristic and
expanding to more advanced methods like CQMs or physics-based optimization as needed. 3. Use
Open3D for the visualization layer, leveraging its efficient rendering and non-blocking update
capabilities for an interactive user experience. 4. Adhere to best practices for integration, paying
meticulous attention to coordinate system alignment and quaternion-to-matrix conversions to
prevent synchronization errors 
. By following this strategic blueprint, it is possible to construct a
powerful, accurate, and user-friendly packaging assistant tailored specifically for the demands of
automotive parts manufacturing.
Reference
PyChrono - An Open-Source Physics Engine - Project Chrono https://projectchrono.org/
pychrono/
How do I calculate collision with rotation in 3D space? - Stack Overflow https://
stackoverflow.com/questions/28487498/how-do-i-calculate-collision-with-rotation-in-3d-space
16 Open-source Physics Simulation Engine - MEDevel.com https://medevel.com/os-physics-
engine/
A Python package for online 3D bin packing optimization by deep ... https://
www.sciencedirect.com/science/article/pii/S2665963824001209
[PDF] A Constructive Heuristic Algorithm for 3D Bin Packing of Irregular ... https://arxiv.org/
pdf/2206.15116
dwave-examples/3d-bin-packing: Use a hybrid solver to ... - GitHub https://github.com/dwave-
examples/3d-bin-packing
How to create an optimized 3D volume-packing function in python? https://stackoverflow.com/
questions/1170478/how-to-create-an-optimized-3d-volume-packing-function-in-python
3d Packing algorithm for item's shipping https://softwareengineering.stackexchange.com/
questions/257977/3d-packing-algorithm-for-items-shipping
12
40
36
28 39
1. 
2. 
3. 
4. 
5. 
6. 
7. 
8. 


# Pàgina 10

Optimizing Space: How Python Revolutionizes Packing Furniture for ... https://medium.com/
@devin.richard.smith/optimizing-space-how-python-revolutionizes-packing-furniture-for-
storage-and-moving-b586d7b494d2
An Open-Source Collision Detection Library Useful for Robotics ... https://github.com/rparak/
Collision_Detection
Containers Loading Optimization with Python | TDS Archive - Medium https://medium.com/
towards-data-science/maximize-the-loading-capacity-of-a-sea-container-to-reduce-your-shipping-
costs-with-python-8cc02c9725a7
Packing optimization of practical systems using a dynamic ... https://jeas.springeropen.com/
articles/10.1186/s44147-024-00426-6
jrouwe/JoltPhysics: A multi core friendly rigid body physics ... - GitHub https://github.com/
jrouwe/JoltPhysics
enthought/mayavi: 3D visualization of scientific data in Python - GitHub https://github.com/
enthought/mayavi
3D collision detection - MDN - Mozilla https://developer.mozilla.org/en-US/docs/Games/
Techniques/3D_collision_detection
3D Collision Detection Library for Python and C++ - MeshLib https://meshlib.io/feature/
collision-detection/
3D Collision Detection with blender. - Python Support https://blenderartists.org/t/3d-collision-
detection-with-blender/630679
Box-box collision detection with PyOpenGL and Pygame at 3d https://stackoverflow.com/
questions/74674884/box-box-collision-detection-with-pyopengl-and-pygame-at-3d
Underhood Spatial Packing and Routing of an Automotive Fuel Cell ... https://arc.aiaa.org/doi/
10.2514/6.2022-0804
Best Scientific 3D Visualization Libraries for Python - Epsilon Forge https://
www.epsilonforge.com/post/best-3d-scientific-visualization/
Using Python to Automate 3D Workflows with OpenUSD https://developer.nvidia.com/blog/
using-python-to-automate-3d-workflows-with-openusd/
3D Scene Graphs Python Tutorial for Spatial AI + LLMs - Medium https://medium.com/data-
science-collective/build-3d-scene-graphs-for-spatial-ai-llms-from-point-cloud-python-tutorial-
c5676caef801
coal-library/coal: An extension of the Flexible Collision Library - GitHub https://github.com/
coal-library/coal
Open 3D Engine Features https://docs.o3de.org/docs/welcome-guide/features-intro/
Documentation | Bullet Real-Time Physics Simulation - PyBullet https://pybullet.org/
wordpress/index.php/forum-2/
9. 
10. 
11. 
12. 
13. 
14. 
15. 
16. 
17. 
18. 
19. 
20. 
21. 
22. 
23. 
24. 
25. 


# Pàgina 11

Interactive visualization — Open3D latest (664eff5) documentation https://www.open3d.org/
docs/latest/tutorial/Advanced/interactive_visualization.html
Integrate scene - Open3D primary (unknown) documentation https://www.open3d.org/docs/
latest/tutorial/reconstruction_system/integrate_scene.html
Pybullet pose in Open3D visualization - python - Stack Overflow https://stackoverflow.com/
questions/71411609/pybullet-pose-in-open3d-visualization
Customized visualization — Open3D latest (664eff5) documentation https://www.open3d.org/
docs/latest/tutorial/Advanced/customized_visualization.html
User Documentation - ReactPhysics3D https://www.reactphysics3d.com/documentation/
Integration of Pybullet with Visualization Toolkit(VTK) - Real-Time ... https://pybullet.org/
Bullet/phpBB3/viewtopic.php?t=12895
DanielChappuis/reactphysics3d: Open source C++ physics ... - GitHub https://github.com/
DanielChappuis/reactphysics3d
ReactPhysics3D - Open-source C++ physics engine https://www.reactphysics3d.com/
FURY - pyBullet Integration Guide https://fury.gl/dev/fury-pybullet.html
Synchronizing Client Server Physics - Real-Time Physics Simulation ... https://pybullet.org/
Bullet/phpBB3/viewtopic.php?t=10006
Visualization — Open3D 0.8.0 documentation https://www.open3d.org/docs/0.8.0/tutorial/
Basic/visualization.html
3D collision for non mathematician https://gamedev.stackexchange.com/questions/101144/3d-
collision-for-non-mathematician
Video Game Physics Tutorial Part II: Collision Detection | Toptal® https://www.toptal.com/
game/video-game-physics-part-ii-collision-detection-for-solid-objects
Transformation — Open3D latest (664eff5) documentation https://www.open3d.org/docs/
latest/tutorial/Basic/transformation.html
Non-blocking visualization - Open3D https://www.open3d.org/docs/latest/tutorial/
visualization/non_blocking_visualization.html
ReactPhysics3D - 3D Physics engine in C++ - Real-Time ... - PyBullet https://pybullet.org/
Bullet/phpBB3/viewtopic.php?t=10462
Wrong transformation when using coordinate frame transform #5473 https://github.com/isl-
org/Open3D/issues/5473
OrientedBoundingBox(OBB)Collision - GitHub https://github.com/SimonDarksideJ/
XNAGameStudio/wiki/OrientedBoundingBox(OBB)Collision
using quaternion for GL rotate - Real-Time Physics Simulation Forum https://pybullet.org/
Bullet/phpBB3/viewtopic.php?t=7482
Implementing Collision Detection & Physics Engine https://hitokageproduction.com/article/11
26. 
27. 
28. 
29. 
30. 
31. 
32. 
33. 
34. 
35. 
36. 
37. 
38. 
39. 
40. 
41. 
42. 
43. 
44. 
45. 


# Pàgina 12

How does a collision engine work? https://gamedev.stackexchange.com/questions/26501/how-
does-a-collision-engine-work
rotation format in bullet physics - Real-Time Physics Simulation Forum https://pybullet.org/
Bullet/phpBB3/viewtopic.php?t=13166
PyBullet Quickstart Guide Inconsistent regarding orientation ... - GitHub https://github.com/
bulletphysics/bullet3/issues/4407
How to set visualization parameter according to quaternion #4208 https://github.com/isl-org/
Open3D/issues/4208
Kivy Rotation from Quaternion (PyBullet) - Stack Overflow https://stackoverflow.com/
questions/48818978/kivy-rotation-from-quaternion-pybullet
Physics - Open 3D Engine - O3DE https://docs.o3de.org/docs/user-guide/interactivity/
physics/
46. 
47. 
48. 
49. 
50. 
51. 


