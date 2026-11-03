# HOI5

The main development target is the native C++ project at the repository root.
The existing Python game is preserved in `H5_Python`.

## Python reference version

From the repository root, run:

```powershell
Set-Location H5_Python
.\.venv\Scripts\python.exe MainMenu.py
```

Run from inside that directory so the existing relative paths for settings,
assets, music and logs resolve as before.

## Native build

Open the repository root as a CMake project in CLion, or use a configured
C++ toolchain and CMake:

```powershell
cmake -S . -B build/cpp
cmake --build build/cpp --config Release
ctest --test-dir build/cpp -C Release --output-on-failure
```

The first configuration fetches SFML 3. The build copies the reference
scenario alongside the executable for automated checks.

New Game generates terrain, deposits, starting borders and capitals in C++. Rendering and camera input run in SFML. Arrows pan, right or middle drag moves the
camera, and the wheel zooms at the cursor.

Space pauses the simulation, 1–5 set its speed, and Escape opens the pause menu.
Left click selects a friendly division. Right click orders it to move on land
or claim neutral land. The time controls also work by mouse.
The map layers button toggles the supply overlay. The toolbar opens the native economy, resources, trade, construction, diplomacy and recruitment panels. The aviation panel forms wings from reserves and assigns targets or rebases them with a right click.

The native port is in progress. The Python version remains the gameplay reference, including for mechanics and panels whose native implementations are partial.
