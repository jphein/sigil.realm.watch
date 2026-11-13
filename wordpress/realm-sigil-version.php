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
        'semver'      => '',  // the contract's semver/build (issue #3): a WordPress install has no git tag to read
        'build'       => '',
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
    // BEGIN sync-words.sh realms: generated from words/realms.json by ./sync-words.sh --only wordpress. Do not edit.
    $realms = [
        'creature' => [
            ['Amber','Bashful','Chittering','Curious','Dappled','Downy','Drowsy','Feathered','Furred','Gentle','Glimmering','Hungry','Inquisitive','Lively','Mossy','Nimble','Plucky','Quick','Restless','Scruffy','Skittish','Speckled','Tufted','Whiskered'],
            ['Sprite','Wisp','Moth','Finch','Wren','Newt','Vole','Hare','Fawn','Cub','Kit','Imp','Pika','Shrew','Marten','Otter','Gecko','Skink','Drake','Wyrmling','Pixie','Brownie','Kelpie','Faun'],
        ],
        'fantasy' => [
            ['Ancient','Arcane','Blazing','Brimming','Celestial','Draconic','Eldritch','Fabled','Gilded','Hallowed','Hollow','Infernal','Jade','Kindled','Luminous','Lunar','Mystic','Mythic','Noble','Obsidian','Primal','Radiant','Runic','Somber','Spectral','Twilight','Valiant','Woven'],
            ['Aegis','Beacon','Crown','Dominion','Echo','Ember','Forge','Grimoire','Herald','Hollow','Insignia','Jewel','Keystone','Lantern','Monolith','Nexus','Oracle','Pinnacle','Pulsar','Quartz','Raven','Relic','Sigil','Throne','Warden'],
        ],
        'fleet' => [
            ['Ancient','Arcane','Argent','Ashen','Blazing','Brimming','Celestial','Draconic','Eldritch','Fabled','Gilded','Hallowed','Hollow','Infernal','Jade','Kindled','Luminous','Lunar','Mystic','Mythic','Noble','Obsidian','Primal','Radiant','Runic','Seraphic','Somber','Spectral','Twilight','Umbral','Valiant','Woven'],
            ['Aegis','Bastion','Brazier','Cairn','Chalice','Citadel','Diadem','Dominion','Echo','Ember','Glyph','Grimoire','Insignia','Jewel','Keystone','Lantern','Lodestar','Monolith','Nexus','Obelisk','Orrery','Pinnacle','Pulsar','Quartz','Raven','Relic','Sanctum','Spire','Talisman','Throne','Vigil','Warden'],
        ],
        'forge' => [
            ['Molten','Hammered','Tempered','Forged','Glowing','Smoldering','Sparking','Kilned','Ironclad','Wrought','Bellowed','Anvilled','White-Hot','Smelted'],
            ['Forge','Anvil','Kiln','Quench','Hammer','Smithy','Smelter','Ironheart','Wright','Crucible','Bellows','Mold','Ingot','Foundry'],
        ],
        'oracle' => [
            ['Augural','Fated','Prescient','Sibylline','Dreaming','Prophetic','Foretold','Whispered','Veiled','Divining','Foreseen','Omened','Occult','Scrying'],
            ['Oracle','Augur','Sibyl','Prophet','Omen','Vision','Harbinger','Dreamer','Seer','Scrying','Prophecy','Runecast','Soothsayer','Divination'],
        ],
        'signal' => [
            ['Amplified','Beaconing','Blinking','Broadcast','Broadcasting','Channeled','Channelled','Decoded','Echoing','Encrypted','Filtered','Grounded','Harmonic','Humming','Isolated','Jittered','Keyed','Latched','Looping','Modulated','Narrowed','Oscillating','Pulsed','Pulsing','Quantized','Relayed','Resonant','Synced','Syncing','Tuned'],
            ['Antenna','Beacon','Broadcast','Carrier','Channel','Diode','Emitter','Frequency','Gate','Harbor','Harmonic','Impulse','Junction','Keystone','Lattice','Lighthouse','Link','Modem','Node','Oscillator','Packet','Ping','Pulsar','Pulse','Qubit','Relay','Semaphore','Signal','Telegraph','Transponder'],
        ],
        'stellar' => [
            ['Stellar','Nebular','Orbital','Cosmic','Gleaming','Supernal','Luminous','Twinkling','Celestial','Gravitational','Eclipsed','Comet-Borne','Equinoctial','Far-Flung'],
            ['Nova','Quasar','Nebula','Comet','Orbit','Solstice','Zenith','Meridian','Constellation','Supernova','Parallax','Lensing','Perihelion','Eclipse'],
        ],
        'tarot' => [
            ['Arcane','Suspended','Towering','Fated','Foolish','Judged','Hierophantic','Crowned','Reversed','Illumined','Querent','Esoteric','Hermetic','Drawn'],
            ['Arcana','Fool','Hierophant','Hanged','Tower','Star','Sun','Moon','Judgement','World','Wheel','Chariot','Hermit','Magician'],
        ],
        'void' => [
            ['Hushed','Unmade','Vacant','Silent','Drifting','Eclipsing','Lost','Shrouded','Fading','Hollowed','Absent','Devoured','Untold','Dimming'],
            ['Abyss','Hollow','Eclipse','Drift','Hush','Shroud','Silence','Chasm','Umbra','Threshold','Rift','Cipher','Vanishment','Absence'],
        ],
    ];
    // END sync-words.sh realms

    $r = isset($realms[$realm]) ? $realms[$realm] : $realms['fantasy'];
    $seed = hexdec(substr($hash, 0, 7));
    $adj = $r[0][$seed % count($r[0])];
    $noun = $r[1][($seed >> 8) % count($r[1])];

    return "$adj $noun · $hash";
}
