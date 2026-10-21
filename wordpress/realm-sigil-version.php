<?php
/**
 * Plugin Name: Realm Sigil Version
 * Description: Adds /wp-json/realm-sigil/v1/version endpoint with deterministic magical names.
 * Version: 1.0.0
 *
 * Must-use plugin — drop into wp-content/mu-plugins/
 *
 * Configure by defining these constants in wp-config.php:
 *   define('REALM_SIGIL_NAME', 'mysite');
 *   define('REALM_SIGIL_DESCRIPTION', 'My site description');
 *   define('REALM_SIGIL_REALM', 'forge');
 *   define('REALM_SIGIL_REPO', 'https://github.com/user/repo');
 */

add_action('rest_api_init', function () {
    register_rest_route('realm-sigil/v1', '/version', [
        'methods'  => 'GET',
        'callback' => 'realm_sigil_version_response',
        'permission_callback' => '__return_true',
    ]);
});

function realm_sigil_version_response() {
    $name = defined('REALM_SIGIL_NAME') ? REALM_SIGIL_NAME : 'wordpress';
    $desc = defined('REALM_SIGIL_DESCRIPTION') ? REALM_SIGIL_DESCRIPTION : get_bloginfo('name');
    $realm = defined('REALM_SIGIL_REALM') ? REALM_SIGIL_REALM : 'fantasy';
    $repo = defined('REALM_SIGIL_REPO') ? REALM_SIGIL_REPO : '';

    global $wp_version;
    $theme = wp_get_theme();
    $hash = substr(md5($wp_version . $theme->get('Version')), 0, 7);
    $version_name = realm_sigil_generate_name($hash, $realm);
    $commit_url = $repo ? $repo . '/commit/' . $hash : '';

    $response = [
        'name'        => $name,
        'description' => $desc,
        'version'     => $version_name,
        'hash'        => $hash,
        'branch'      => 'production',
        'dirty'       => false,
        'built'       => gmdate('Y-m-d\TH:i:s\Z', filemtime(ABSPATH . 'wp-includes/version.php')),
        'started'     => gmdate('Y-m-d\TH:i:s\Z', $_SERVER['REQUEST_TIME']),
        'uptime'      => time() - $_SERVER['REQUEST_TIME'],
        'realm'       => $realm,
        'runtime'     => 'php' . PHP_VERSION,
        'os'          => PHP_OS . '/' . php_uname('m'),
        'host'        => gethostname(),
        'pid'         => getmypid(),
        'repo'        => $repo,
        'commit_url'  => $commit_url,
        'wp_version'  => $wp_version,
        'theme'       => $theme->get('Name') . ' ' . $theme->get('Version'),
    ];

    // Optional server-only field: the root filesystem's size and free space, so a fleet view
    // (realmwatch /updates/fleet) can flag a filling disk. Inside the wordpress container `/` is
    // overlayfs, and statfs on it reports the HOST's root filesystem (verified on tow2 2026-10-21:
    // container and host df agree). free_bytes is what non-root can still write (df's Avail);
    // used_pct = 1 - free/total, so it reads about 1 point under df's Use% (root-reserved blocks).
    // PHP 8 removes functions listed in disable_functions, and calling one throws, so check first:
    // a host that disables them just omits the field instead of breaking the whole endpoint.
    if (function_exists('disk_total_space') && function_exists('disk_free_space')) {
        try {
            $total = @disk_total_space('/');
            $free = @disk_free_space('/');
            if ($total && $free !== false) {
                $response['disk'] = [
                    'path'        => '/',
                    'total_bytes' => (int) $total,
                    'free_bytes'  => (int) $free,
                    'used_pct'    => round(100 * (1 - $free / $total), 1),
                ];
            }
        } catch (\Throwable $e) {
            // optional field: leave it out
        }
    }

    return new WP_REST_Response($response, 200, [
        'Cache-Control' => 'no-cache',
        'Access-Control-Allow-Origin' => '*',
    ]);
}

function realm_sigil_generate_name($hash, $realm) {
    $realms = [
        'fantasy' => [
            ['Arcane','Blazing','Celestial','Draconic','Eldritch','Fabled','Gilded','Hallowed','Infernal','Jade','Kindled','Luminous','Mythic','Noble','Obsidian','Primal','Radiant','Spectral','Twilight','Valiant'],
            ['Aegis','Beacon','Crown','Dominion','Ember','Forge','Grimoire','Herald','Insignia','Jewel','Keystone','Lantern','Monolith','Nexus','Oracle','Pinnacle','Quartz','Relic','Sigil','Throne'],
        ],
        'tarot' => [
            ['Arcane','Blessed','Charmed','Destined','Enchanted','Fateful','Guiding','Hidden','Illumined','Judging','Karmic','Liminal','Moonlit','Numbered','Ordained','Portentous','Querent','Reversed','Starlit','Turning'],
            ['Amulet','Blade','Chalice','Diviner','Emperor','Fool','Guardian','Hermit','Initiate','Justice','Knight','Lovers','Magician','Nomad','Ouroboros','Pentacle','Querent','Rosette','Scepter','Tower'],
        ],
        'oracle' => [
            ['Augured','Beckoning','Clairvoyant','Delphic','Ethereal','Foretold','Glimpsed','Hushed','Intuited','Judicious','Knowing','Lucid','Murmured','Nascent','Omniscient','Prophetic','Quieted','Resonant','Scried','Veiled'],
            ['Augury','Bones','Cipher','Doctrine','Echo','Foresight','Gaze','Hymn','Insight','Judgment','Kenning','Lens','Mirror','Notion','Omen','Prophecy','Question','Revelation','Sight','Truth'],
        ],
        'void' => [
            ['Abyssal','Boundless','Collapsed','Drifting','Entropic','Fractured','Galactic','Hollow','Infinite','Jagged','Kinetic','Liminal','Muted','Null','Obsidian','Phantom','Quantum','Ruptured','Silent','Twisted'],
            ['Abyss','Breach','Cascade','Drift','Expanse','Fragment','Glitch','Horizon','Interval','Junction','Knot','Lattice','Membrane','Nexus','Orbit','Paradox','Rift','Shade','Threshold','Vertex'],
        ],
        'forge' => [
            ['Annealed','Bolted','Carbonized','Dense','Electric','Flux','Galvanized','Hardened','Ignited','Joined','Keen','Laminated','Molten','Nitrided','Oxidized','Pressed','Quenched','Riveted','Sintered','Tempered'],
            ['Anvil','Bellows','Crucible','Die','Engine','Furnace','Gear','Hammer','Ingot','Jig','Kiln','Lathe','Mandrel','Nozzle','Oven','Piston','Quench','Rivet','Spark','Tongs'],
        ],
        'signal' => [
            ['Amplified','Broadcast','Channeled','Decoded','Echoing','Filtered','Grounded','Harmonic','Isolated','Jittered','Keyed','Latched','Modulated','Narrowed','Oscillating','Pulsed','Quantized','Relayed','Synced','Tuned'],
            ['Antenna','Beacon','Carrier','Diode','Emitter','Frequency','Gate','Harmonic','Impulse','Junction','Keystone','Link','Modem','Node','Oscillator','Pulse','Qubit','Relay','Signal','Transponder'],
        ],
        'stellar' => [
            ['Ascending','Binary','Cosmic','Distant','Expanding','Flaring','Graviton','Helical','Ionized','Jovian','Kepler','Lunar','Magnetic','Nebular','Orbital','Pulsating','Quantum','Radiant','Solar','Tidal'],
            ['Aurora','Bolide','Corona','Dwarf','Eclipse','Firmament','Galaxy','Halo','Ion','Jet','Kuiper','Luminance','Meteor','Nova','Orbit','Pulsar','Quasar','Remnant','Supernova','Zenith'],
        ],
    ];

    $r = isset($realms[$realm]) ? $realms[$realm] : $realms['fantasy'];
    $seed = hexdec(substr($hash, 0, 7));
    $adj = $r[0][$seed % count($r[0])];
    $noun = $r[1][($seed >> 8) % count($r[1])];

    return "$adj $noun · $hash";
}
