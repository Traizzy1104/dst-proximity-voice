-- Proximity Voice (Mumble Bridge)
-- DST Client Mod

local GLOBAL = GLOBAL
local print = GLOBAL.print
local tostring = GLOBAL.tostring
local math = GLOBAL.math
local GetTime = GLOBAL.GetTime

print("[MUMBLE_LINK] Mod wird geladen...")

local UPDATE_INTERVAL = 0.05 -- 20x pro Sekunde auf Bewegung und Kameradrehung pruefen
local KEEPALIVE_INTERVAL = 1.0 -- Alle 1s senden, wenn man stillsteht

local last_x = 0
local last_y = 0
local last_z = 0
local last_rot = 0
local last_cam = 0
local last_time = 0
local last_ghost = false
local last_cave = false
local task_started = false

local function UpdateMumblePosition()
    local player = GLOBAL.ThePlayer
    if not (player and player.Transform and player:IsValid()) then
        return
    end

    local x, y, z = player.Transform:GetWorldPosition()
    local rot = player.Transform:GetRotation() or 0
    local is_ghost = player:HasTag("playerghost")
    local world = GLOBAL.TheWorld
    local is_cave = (world and world:HasTag("cave")) or false

    -- Kamerawinkel auslesen (reagiert auf Q und E)
    local camera = GLOBAL.TheCamera
    local cam_heading = camera and camera:GetHeading() or 0

    local now = GetTime and GetTime() or 0

    -- Delta-Check: Hat sich Position, Blickrichtung oder die Kamera mit Q/E gedreht?
    local dx = x - last_x
    local dz = z - last_z
    local dist_sq = dx * dx + dz * dz

    local rot_diff = math.abs(rot - last_rot)
    if rot_diff > 180 then
        rot_diff = 360 - rot_diff
    end

    local cam_diff = math.abs(cam_heading - last_cam)
    if cam_diff > 180 then
        cam_diff = 360 - cam_diff
    end

    local state_changed = (is_ghost ~= last_ghost) or (is_cave ~= last_cave)
    local moved = dist_sq > 0.01 or rot_diff > 2.0 or cam_diff > 1.0 or state_changed
    local keepalive_due = (now - last_time) >= KEEPALIVE_INTERVAL

    if moved or keepalive_due then
        last_x = x
        last_y = y
        last_z = z
        last_rot = rot
        last_cam = cam_heading
        last_ghost = is_ghost
        last_cave = is_cave
        last_time = now

        local adjusted_z = z
        if is_cave then
            adjusted_z = z + 50000.0
        end

        print(string.format("[MUMBLE_LINK] POS:%.2f,%.2f,%.2f ROT:%.2f CAM:%.2f GHOST:%s", 
            x, y, adjusted_z, rot, cam_heading, tostring(is_ghost)))
    end
end

local function StartTracking(inst)
    if task_started then return end
    task_started = true
    print("[MUMBLE_LINK] Tracking-Task mit Kamera-Support gestartet!")
    inst:DoPeriodicTask(UPDATE_INTERVAL, UpdateMumblePosition)
end

AddPrefabPostInit("world", StartTracking)
AddPrefabPostInit("forest", StartTracking)
AddPrefabPostInit("cave", StartTracking)

AddPlayerPostInit(function(inst)
    inst:DoTaskInTime(0.5, function()
        if inst == GLOBAL.ThePlayer then
            StartTracking(inst)
        end
    end)
end)
