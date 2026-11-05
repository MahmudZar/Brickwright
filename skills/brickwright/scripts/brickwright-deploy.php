<?php
/**
 * Brickwright server functions. Fixed, tested code: agents run it, they never rewrite it.
 *
 * Load it, any of:
 *   - one-shot (nothing installed): `deploy.py prepare --one-shot` uploads this file with the bundle,
 *     the call checks its md5, loads it from a temp file for one request and deletes it.
 *   - installed: copy to wp-content/mu-plugins/, or paste (without the opening tag) into a
 *     code-snippets plugin.
 *
 * Functions (call from an execute-php ability: Novamira `execute-php`, Bricks `bricks/execute-php`):
 *   brickwright_deploy( [ 'file' => 'brickwright-import/<piece>.bundle.b64.txt', 'md5' => '...' ] )
 *       Options: data (bundle passed inline instead of a file, base64 or JSON), dry_run, adopt,
 *       force, backup_dir, delete_file (default true; the upload is deleted after a real run,
 *       whether it succeeded or failed).
 *   brickwright_restore( [ 'stamp' => '20261105-140119', 'backup_dir' => '...', 'dry_run' => true ] )
 *   brickwright_site_config()   components, variables, classes, locked classes, Bricks settings
 *   brickwright_render( [ 'post_id' => 14, 'area' => 'content', 'grep' => [ 'word' ], 'expect' => [ 'abcdef' ] ] )
 *
 * Deploy steps: read + md5 check -> back up classes and targets -> map class names to ids ->
 * refuse locked classes and anything edited on the site since the last deploy -> Bricks' save
 * pipeline dry run (its validator) -> write classes (+ Bricks' class timestamp) -> Bricks' save
 * pipeline per target (revision, CSS regeneration, unchanged = no-op) -> CSS files rebuilt when
 * Bricks loads CSS from files -> new digests for the local record -> page caches purged.
 */

if ( ! defined( 'BRICKWRIGHT_SERVER_VERSION' ) ) {
	define( 'BRICKWRIGHT_SERVER_VERSION', '0.2.0' );
}

if ( ! function_exists( 'brickwright_deploy' ) ) {

	function brickwright_deploy( array $args ) {
		$dry  = ! empty( $args['dry_run'] );
		$path = isset( $args['data'] ) ? '' : brickwright_resolve_path( (string) ( $args['file'] ?? '' ) );
		try {
			$report = brickwright_deploy_run( $args, $path );
		} catch ( \Throwable $e ) {
			$report = [ 'ok' => false, 'dry_run' => $dry, 'error' => 'PHP error: ' . $e->getMessage() . ' (' . basename( $e->getFile() ) . ':' . $e->getLine() . ')' ];
		}
		// Uploads are public: a real run removes the bundle whatever happened. A dry run keeps it for the real run.
		if ( ! $dry && $path && ( $args['delete_file'] ?? true ) && file_exists( $path ) ) {
			@unlink( $path );
		}
		if ( $path ) {
			$report['upload_deleted'] = ! file_exists( $path );
		}
		$report['server_version'] = BRICKWRIGHT_SERVER_VERSION;
		return $report;
	}

	function brickwright_deploy_run( array $args, string $path ) {
		$report = [ 'ok' => false, 'dry_run' => ! empty( $args['dry_run'] ) ];

		if ( is_multisite() && empty( $args['allow_multisite'] ) ) {
			return brickwright_fail( $report, 'multisite is untested: Bricks may keep global classes on the main site. Pass allow_multisite => true only after checking.' );
		}
		if ( ! defined( 'BRICKS_VERSION' ) ) {
			return brickwright_fail( $report, 'Bricks is not active on this site' );
		}

		// 1. Read the bundle.
		if ( isset( $args['data'] ) ) {
			$raw = trim( (string) $args['data'] );
			if ( '' !== $raw && '{' !== $raw[0] ) {
				$raw = base64_decode( preg_replace( '/\s+/', '', $raw ), true );
			}
		} else {
			if ( ! $path || ! is_readable( $path ) ) {
				return brickwright_fail( $report, 'bundle not found: ' . ( $args['file'] ?? '(no file given)' ) );
			}
			$raw = file_get_contents( $path );
			if ( substr( $path, -8 ) === '.b64.txt' ) {
				$raw = base64_decode( preg_replace( '/\s+/', '', $raw ), true );
			}
		}
		if ( false === $raw || '' === $raw ) {
			return brickwright_fail( $report, 'bundle is empty or not valid base64' );
		}
		if ( ! empty( $args['md5'] ) && md5( $raw ) !== $args['md5'] ) {
			return brickwright_fail( $report, 'md5 mismatch (file changed or upload incomplete): got ' . md5( $raw ) );
		}
		$bundle = json_decode( $raw, true );
		if ( ! is_array( $bundle ) || ( $bundle['format'] ?? '' ) !== 'brickwright-bundle/1' ) {
			return brickwright_fail( $report, 'not a brickwright-bundle/1 file' );
		}
		$new_classes = (array) ( $bundle['classes'] ?? [] );
		$trees       = (array) ( $bundle['trees'] ?? [] );
		$targets     = (array) ( $bundle['targets'] ?? [] );
		$previous    = (array) ( $bundle['previous'] ?? [] );
		$preserve    = (array) ( $bundle['preserve'] ?? [] );
		$adopt       = ! empty( $args['adopt'] );
		$force       = ! empty( $args['force'] );
		$report['piece'] = $bundle['piece'] ?? null;
		foreach ( array_keys( $trees ) as $name ) {
			$pid = (int) ( $targets[ $name ]['post_id'] ?? 0 );
			if ( ! $pid ) {
				return brickwright_fail( $report, "tree `$name` has no target post_id" );
			}
			if ( ! get_post( $pid ) ) {
				return brickwright_fail( $report, "target post $pid for `$name` doesn't exist (create the page or template first)" );
			}
			if ( ! in_array( $targets[ $name ]['area'] ?? 'content', [ 'content', 'header', 'footer' ], true ) ) {
				return brickwright_fail( $report, "tree `$name`: area must be content, header or footer" );
			}
		}

		// 2. Back up.
		$classes = get_option( 'bricks_global_classes', [] );
		$classes = is_array( $classes ) ? array_values( $classes ) : [];
		$bdir    = rtrim( (string) ( $args['backup_dir'] ?? brickwright_default_backup_dir() ), '/' );
		if ( ! $report['dry_run'] ) {
			if ( ! is_dir( $bdir ) && ! wp_mkdir_p( $bdir ) ) {
				return brickwright_fail( $report, "can't create backup folder $bdir" );
			}
			$stamp = gmdate( 'Ymd-His' );
			while ( file_exists( "$bdir/$stamp-brickwright-global-classes.json" ) ) {
				$stamp .= 'b';
			}
			$saved = false !== file_put_contents( "$bdir/$stamp-brickwright-global-classes.json", wp_json_encode( $classes ) );
			foreach ( $trees as $name => $_ ) {
				$t     = $targets[ $name ];
				$key   = brickwright_meta_key( $t['area'] ?? 'content' );
				$saved = $saved && false !== file_put_contents(
					"$bdir/$stamp-brickwright-post-{$t['post_id']}-$key.json",
					wp_json_encode( get_post_meta( (int) $t['post_id'], $key, true ) )
				);
			}
			if ( ! $saved ) {
				return brickwright_fail( $report, "backup to $bdir failed: nothing written" );
			}
			$report['backup'] = [ 'dir' => $bdir, 'stamp' => $stamp ];
		}

		// 3. Classes: map names to ids, find changes, refuse locked classes and drift.
		$locked  = array_flip( array_map( 'strval', (array) get_option( 'bricks_global_classes_locked', [] ) ) );
		$by_name = [];
		foreach ( $classes as $i => $c ) {
			if ( isset( $c['name'] ) ) {
				$by_name[ $c['name'] ] = $i;
			}
		}
		$taken     = array_column( $classes, 'id' );
		$map       = [];
		$conflicts = [];
		$changes   = [ 'added' => [], 'updated' => [], 'unchanged' => 0 ];
		$prev_cls  = (array) ( $previous['classes'] ?? [] );
		$now_ms    = (int) round( microtime( true ) * 1000 );
		foreach ( $new_classes as $name => $css ) {
			if ( ! is_string( $name ) || ! preg_match( '/^-?[_a-zA-Z][\w-]*$/', $name ) ) {
				return brickwright_fail( $report, "invalid class name: $name" );
			}
			if ( isset( $by_name[ $name ] ) ) {
				$i    = $by_name[ $name ];
				$live = (string) ( $classes[ $i ]['settings']['_cssCustom'] ?? '' );
				$map[ $name ] = $classes[ $i ]['id'];
				if ( $live === $css ) {
					$changes['unchanged']++;
					continue;
				}
				if ( isset( $locked[ (string) $classes[ $i ]['id'] ] ) ) {
					$conflicts[] = "class `$name` is locked in Bricks (usually a framework class): Brickwright never changes locked classes. Rename your class.";
					continue;
				}
				$known = $prev_cls[ $name ] ?? null;
				if ( ! $force && ( ( $known && $known !== md5( $live ) ) || ( ! $known && ! $adopt ) ) ) {
					$conflicts[] = $known
						? "class `$name` was changed on the site since the last deploy: pull the change into your files first (or force)"
						: "class `$name` already exists and Brickwright never deployed it: compare it, then deploy with adopt";
					continue;
				}
				$classes[ $i ]['settings']['_cssCustom'] = $css;
				$classes[ $i ]['modified']               = $now_ms;
				$changes['updated'][]                    = $name;
				continue;
			}
			do {
				$id = substr( str_shuffle( 'abcdefghijklmnopqrstuvwxyz0123456789' ), 0, 6 );
			} while ( in_array( $id, $taken, true ) || ctype_digit( $id[0] ) );
			$taken[]          = $id;
			$classes[]        = [ 'id' => $id, 'name' => $name, 'settings' => [ '_cssCustom' => $css ], 'modified' => $now_ms, 'user_id' => get_current_user_id() ];
			$map[ $name ]     = $id;
			$by_name[ $name ] = count( $classes ) - 1;
			$changes['added'][] = $name;
		}
		foreach ( $classes as $c ) {
			if ( isset( $c['name'] ) && ! isset( $map[ $c['name'] ] ) ) {
				$map[ $c['name'] ] = $c['id'];
			}
		}
		$report['classes'] = [ 'added' => $changes['added'], 'updated' => $changes['updated'], 'unchanged' => $changes['unchanged'] ];

		// 4. Trees: map classes, merge into the target, drift check, Bricks dry run.
		$plans = [];
		foreach ( $trees as $name => $els ) {
			$t        = $targets[ $name ];
			$post_id  = (int) $t['post_id'];
			$area     = (string) ( $t['area'] ?? 'content' );
			$mode     = (string) ( $t['mode'] ?? 'section' );
			$key      = brickwright_meta_key( $area );
			$existing = get_post_meta( $post_id, $key, true );
			$existing = is_array( $existing ) ? array_values( $existing ) : [];
			$missing  = [];
			if ( ! in_array( $mode, [ 'section', 'replace' ], true ) ) {
				return brickwright_fail( $report, "tree `$name`: mode must be section or replace" );
			}
			foreach ( $els as &$e ) {
				$e['parent'] = brickwright_is_root( $e['parent'] ?? 0 ) ? 0 : $e['parent'];
				if ( ! empty( $e['settings']['_cssGlobalClasses'] ) ) {
					$e['settings']['_cssGlobalClasses'] = array_values( array_map(
						function ( $n ) use ( $map, &$missing ) {
							$k = ltrim( (string) $n, '@' );
							if ( ! isset( $map[ $k ] ) ) {
								$missing[] = $k;
							}
							return $map[ $k ] ?? $k;
						},
						$e['settings']['_cssGlobalClasses']
					) );
				}
			}
			unset( $e );
			if ( $missing ) {
				return brickwright_fail( $report, "`$name` uses classes that exist nowhere: " . implode( ', ', array_unique( $missing ) ) );
			}

			// The part of the live page this tree owns: its roots' current subtrees.
			$roots    = array_values( array_map( fn( $e ) => $e['id'], array_filter( $els, fn( $e ) => brickwright_is_root( $e['parent'] ) ) ) );
			$live_ids = 'replace' === $mode ? array_column( $existing, 'id' ) : brickwright_subtree_ids( $existing, $roots );
			$live_sub = array_values( array_filter( $existing, fn( $e ) => in_array( $e['id'], $live_ids, true ) ) );
			$known    = $previous['trees'][ $name ] ?? null;
			if ( $live_sub && ! $force ) {
				$live_digest = brickwright_digest( $live_sub );
				if ( $known && $known !== $live_digest ) {
					$conflicts[] = "`$name` on post $post_id was edited on the site since the last deploy: pull the change into your files first (or force)";
				} elseif ( ! $known && ! $adopt ) {
					$conflicts[] = "`$name` replaces " . count( $live_sub ) . " existing element(s) on post $post_id that Brickwright never deployed: check them, then deploy with adopt";
				}
			}

			// Keep live settings of preserved elements under ours (e.g. WooCommerce element options).
			$live_by_id = array_column( $existing, null, 'id' );
			foreach ( $els as &$e ) {
				if ( in_array( $e['id'], (array) ( $preserve[ $name ] ?? [] ), true ) && isset( $live_by_id[ $e['id'] ] ) ) {
					$own = (array) ( $live_by_id[ $e['id'] ]['settings'] ?? [] );
					unset( $own['_cssGlobalClasses'] );
					$e['settings'] = array_merge( $own, (array) $e['settings'] );
				}
			}
			unset( $e );

			// Merge: replace the whole area, or swap our subtree in place (other sections untouched).
			if ( 'replace' === $mode ) {
				$merged = $els;
			} else {
				$position = null;
				$kept     = [];
				foreach ( $existing as $e ) {
					if ( in_array( $e['id'], $live_ids, true ) ) {
						$position = $position ?? count( $kept );
						continue;
					}
					$kept[] = $e;
				}
				$kept_ids = array_column( $kept, 'id' );
				foreach ( $els as $e ) {
					if ( in_array( $e['id'], $kept_ids, true ) ) {
						return brickwright_fail( $report, "`$name`: element id {$e['id']} is already used elsewhere on post $post_id (change the build seed)" );
					}
				}
				if ( null === $position ) {
					$position = count( $kept );
					if ( ! empty( $t['after'] ) ) {
						if ( ! in_array( $t['after'], $kept_ids, true ) ) {
							return brickwright_fail( $report, "`$name`: 'after' element {$t['after']} is not on post $post_id" );
						}
						$after_ids = brickwright_subtree_ids( $kept, [ $t['after'] ] );
						foreach ( $kept as $k => $e ) {
							if ( in_array( $e['id'], $after_ids, true ) ) {
								$position = $k + 1;
							}
						}
					}
				}
				$merged = array_merge( array_slice( $kept, 0, $position ), $els, array_slice( $kept, $position ) );
			}

			$plans[ $name ] = compact( 'post_id', 'area', 'key', 'existing', 'merged', 'roots', 'mode' );
		}

		if ( $conflicts ) {
			$report['conflicts'] = $conflicts;
			return brickwright_fail( $report, count( $conflicts ) . ' conflict(s): nothing written' );
		}

		$pipeline = class_exists( '\Bricks\Abilities\Save_Pipeline' );
		$report['bricks_save_pipeline'] = $pipeline;
		if ( ! $pipeline ) {
			$report['warning'] = 'Bricks save pipeline not found (Bricks older than 2.4?): data is saved without Bricks validation.';
		}
		foreach ( $plans as $name => $p ) {
			if ( $pipeline ) {
				$dry = \Bricks\Abilities\Save_Pipeline::dry_run( $p['post_id'], $p['merged'], $p['area'], [], false, [ 'workspaceBaselineElements' => $p['existing'] ] );
				if ( is_wp_error( $dry ) ) {
					return brickwright_fail( $report, "Bricks rejected `$name`: " . brickwright_error_text( $dry ) );
				}
			}
			$report['trees'][ $name ] = [ 'post_id' => $p['post_id'], 'area' => $p['area'], 'mode' => $p['mode'], 'elements' => count( $trees[ $name ] ), 'page_elements_after' => count( $p['merged'] ), 'replaces' => count( $p['existing'] ) - ( count( $p['merged'] ) - count( $trees[ $name ] ) ) ];
		}

		if ( $report['dry_run'] ) {
			$report['ok'] = true;
			return $report;
		}

		// 5. Write classes (and tell open builders they changed), then each target.
		$classes_changed = $changes['added'] || $changes['updated'];
		if ( $classes_changed ) {
			update_option( 'bricks_global_classes', $classes );
			update_option( 'bricks_global_classes_timestamp', time() );
			update_option( 'bricks_global_classes_user', get_current_user_id() );
		}
		$record = [ 'classes' => [], 'trees' => [] ];
		foreach ( $new_classes as $name => $_ ) {
			$record['classes'][ $name ] = md5( (string) ( $classes[ $by_name[ $name ] ]['settings']['_cssCustom'] ?? '' ) );
		}
		foreach ( $plans as $name => $p ) {
			if ( $pipeline ) {
				$res = \Bricks\Abilities\Save_Pipeline::execute( $p['post_id'], $p['merged'], $p['area'], [], '', false, [ 'workspaceBaselineElements' => $p['existing'] ] );
				if ( is_wp_error( $res ) ) {
					$report['classes_already_written'] = $classes_changed;
					return brickwright_fail( $report, "Bricks couldn't save `$name`: " . brickwright_error_text( $res ) . '. Restore with brickwright_restore([\'stamp\' => \'' . $report['backup']['stamp'] . '\']) if needed.' );
				}
				$report['trees'][ $name ]['changed']  = (bool) ( $res['changed'] ?? true );
				$report['trees'][ $name ]['revision'] = $res['revisionId'] ?? null;
			} else {
				update_post_meta( $p['post_id'], $p['key'], $p['merged'] );
				wp_update_post( [ 'ID' => $p['post_id'] ] );
				$report['trees'][ $name ]['changed'] = true;
			}
			if ( 'content' === $p['area'] ) {
				update_post_meta( $p['post_id'], '_bricks_editor_mode', 'bricks' );
			}
			wp_cache_delete( $p['post_id'], 'post_meta' );
			$saved = get_post_meta( $p['post_id'], $p['key'], true );
			$saved = is_array( $saved ) ? array_values( $saved ) : [];
			$ids   = 'replace' === $p['mode'] ? array_column( $saved, 'id' ) : brickwright_subtree_ids( $saved, $p['roots'] );
			$record['trees'][ $name ] = brickwright_digest( array_values( array_filter( $saved, fn( $e ) => in_array( $e['id'], $ids, true ) ) ) );
			$report['trees'][ $name ]['saved_elements'] = count( $ids );
		}
		$report['record'] = $record;

		// 6. Bricks writing CSS to files: a class change affects every page that uses it.
		if ( $classes_changed && 'file' === \Bricks\Database::get_setting( 'cssLoading', 'inline' ) ) {
			$report['css_files'] = brickwright_regenerate_css_files();
		}
		brickwright_purge_caches();
		do_action( 'brickwright_deployed', $report );
		$report['ok'] = true;
		return $report;
	}

	/** Put back the classes and pages saved by one deploy's backup. Backs up the current state first. */
	function brickwright_restore( array $args ) {
		$bdir  = rtrim( (string) ( $args['backup_dir'] ?? brickwright_default_backup_dir() ), '/' );
		$stamp = preg_replace( '/[^0-9a-z-]/', '', (string) ( $args['stamp'] ?? '' ) );
		$files = $stamp ? glob( "$bdir/$stamp-brickwright-*.json" ) : [];
		if ( ! $files ) {
			return [ 'ok' => false, 'error' => "no backup files for stamp '$stamp' in $bdir" ];
		}
		$plan = [];
		foreach ( $files as $f ) {
			if ( preg_match( '/-brickwright-global-classes\.json$/', $f ) ) {
				$plan[] = [ 'type' => 'classes', 'file' => $f ];
			} elseif ( preg_match( '/-brickwright-post-(\d+)-(_bricks_page_(?:content|header|footer)_2)\.json$/', $f, $m ) ) {
				$plan[] = [ 'type' => 'post', 'file' => $f, 'post_id' => (int) $m[1], 'key' => $m[2] ];
			}
		}
		$report = [ 'ok' => true, 'dry_run' => ! empty( $args['dry_run'] ), 'restores' => array_map( fn( $p ) => basename( $p['file'] ), $plan ) ];
		if ( $report['dry_run'] ) {
			return $report;
		}
		$now = gmdate( 'Ymd-His' ) . '-before-restore';
		foreach ( $plan as $p ) {
			$data = json_decode( (string) file_get_contents( $p['file'] ), true );
			if ( 'classes' === $p['type'] ) {
				file_put_contents( "$bdir/$now-brickwright-global-classes.json", wp_json_encode( get_option( 'bricks_global_classes', [] ) ) );
				update_option( 'bricks_global_classes', is_array( $data ) ? $data : [] );
				update_option( 'bricks_global_classes_timestamp', time() );
			} else {
				file_put_contents( "$bdir/$now-brickwright-post-{$p['post_id']}-{$p['key']}.json", wp_json_encode( get_post_meta( $p['post_id'], $p['key'], true ) ) );
				if ( is_array( $data ) && $data ) {
					update_post_meta( $p['post_id'], $p['key'], $data );
				} else {
					delete_post_meta( $p['post_id'], $p['key'] );
				}
				wp_update_post( [ 'ID' => $p['post_id'] ] );
			}
		}
		if ( 'file' === \Bricks\Database::get_setting( 'cssLoading', 'inline' ) ) {
			$report['css_files'] = brickwright_regenerate_css_files();
		}
		brickwright_purge_caches();
		$report['current_state_saved_as'] = $now;
		return $report;
	}

	/** What a build needs to know about the site: components, design tokens, classes. */
	function brickwright_site_config() {
		$slug = fn( $s ) => trim( preg_replace( '/[^a-z0-9]+/', '-', strtolower( (string) $s ) ), '-' );
		$out  = [ 'format' => 'brickwright-site/1', 'exported' => gmdate( 'c' ), 'site' => home_url(), 'bricks_version' => defined( 'BRICKS_VERSION' ) ? BRICKS_VERSION : null ];
		$out['components'] = [];
		foreach ( (array) get_option( 'bricks_components', [] ) as $c ) {
			$name  = $slug( $c['label'] ?? ( $c['elements'][0]['label'] ?? $c['id'] ) );
			$props = [];
			foreach ( (array) ( $c['properties'] ?? [] ) as $p ) {
				$key = $slug( $p['label'] ?? $p['id'] );
				if ( 0 === strpos( $key, $name . '-' ) && strlen( $key ) > strlen( $name ) + 1 ) {
					$key = substr( $key, strlen( $name ) + 1 );
				}
				$props[ $key ] = $p['id'];
			}
			$out['components'][ $name ] = [ 'cid' => $c['id'], 'props' => $props ];
		}
		$out['tokens']  = array_values( array_map( fn( $v ) => '--' . ltrim( (string) $v['name'], '-' ), array_filter( (array) get_option( 'bricks_global_variables', [] ), fn( $v ) => ! empty( $v['name'] ) ) ) );
		$classes        = (array) get_option( 'bricks_global_classes', [] );
		$locked         = array_flip( array_map( 'strval', (array) get_option( 'bricks_global_classes_locked', [] ) ) );
		$out['classes'] = array_values( array_map( fn( $c ) => $c['name'], array_filter( $classes, fn( $c ) => isset( $c['name'] ) ) ) );
		$out['locked_classes'] = array_values( array_map( fn( $c ) => $c['name'], array_filter( $classes, fn( $c ) => isset( $c['name'], $c['id'] ) && isset( $locked[ (string) $c['id'] ] ) ) ) );
		$out['settings'] = class_exists( '\Bricks\Database' ) ? [
			'css_loading'    => \Bricks\Database::get_setting( 'cssLoading', 'inline' ),
			'code_execution' => (bool) \Bricks\Database::get_setting( 'executeCodeEnabled' ),
			'save_pipeline'  => class_exists( '\Bricks\Abilities\Save_Pipeline' ),
			'multisite'      => is_multisite(),
		] : [];
		return $out;
	}

	/** Render a target server-side (no HTTP, works for drafts and behind bot checks) and check it. */
	function brickwright_render( array $args ) {
		$post_id = (int) ( $args['post_id'] ?? 0 );
		$els     = get_post_meta( $post_id, brickwright_meta_key( (string) ( $args['area'] ?? 'content' ) ), true );
		if ( ! is_array( $els ) || ! $els || ! class_exists( '\Bricks\Frontend' ) ) {
			return [ 'ok' => false, 'error' => "nothing to render on post $post_id" ];
		}
		$html = \Bricks\Frontend::render_data( $els );
		$out  = [ 'ok' => true, 'bytes' => strlen( $html ), 'elements' => count( $els ), 'found_words' => [], 'missing_ids' => [] ];
		foreach ( (array) ( $args['grep'] ?? [] ) as $w ) {
			if ( '' !== $w && false !== stripos( $html, (string) $w ) ) {
				$out['found_words'][] = $w;
			}
		}
		foreach ( (array) ( $args['expect'] ?? [] ) as $id ) {
			if ( false === strpos( $html, (string) $id ) ) {
				$out['missing_ids'][] = $id;
			}
		}
		if ( ! empty( $args['html'] ) ) {
			$out['html'] = $html;
		}
		$out['ok'] = ! $out['found_words'] && ! $out['missing_ids'];
		return $out;
	}

	function brickwright_regenerate_css_files() {
		if ( defined( 'BRICKS_PATH' ) ) {
			foreach ( [ 'color-palettes', 'global-custom-css', 'global-elements', 'theme-styles', 'global-variables', 'files' ] as $f ) {
				$file = BRICKS_PATH . "includes/assets/$f.php";
				if ( file_exists( $file ) ) {
					require_once $file;
				}
			}
		}
		if ( ! class_exists( '\Bricks\Assets_Files' ) || ! method_exists( '\Bricks\Assets_Files', 'regenerate_css_files' ) ) {
			return 'not regenerated: Bricks Assets_Files not found. Regenerate in Bricks > Settings > Performance.';
		}
		$files = \Bricks\Assets_Files::regenerate_css_files();
		return is_array( $files ) ? count( $files ) . ' file(s) regenerated' : 'regenerated';
	}

	function brickwright_purge_caches() {
		do_action( 'litespeed_purge_all' );
		if ( function_exists( 'rocket_clean_domain' ) ) {
			rocket_clean_domain();
		}
		if ( function_exists( 'w3tc_flush_all' ) ) {
			w3tc_flush_all();
		}
		if ( function_exists( 'wp_cache_clear_cache' ) ) {
			wp_cache_clear_cache();
		}
		if ( function_exists( 'sg_cachepress_purge_cache' ) ) {
			sg_cachepress_purge_cache();
		}
		do_action( 'brickwright_purge_cache' );
	}

	function brickwright_fail( array $report, string $message ) {
		$report['ok']    = false;
		$report['error'] = $message;
		return $report;
	}

	function brickwright_resolve_path( string $file ) {
		if ( '' === $file ) {
			return '';
		}
		if ( '/' === $file[0] || preg_match( '/^[A-Za-z]:[\\\\\/]/', $file ) ) {
			return $file;
		}
		$uploads = wp_upload_dir()['basedir'];
		return file_exists( "$uploads/$file" ) ? "$uploads/$file" : ABSPATH . ltrim( $file, '/' );
	}

	function brickwright_default_backup_dir() {
		$dir = WP_CONTENT_DIR . '/brickwright-backups';
		if ( ! is_dir( $dir ) && wp_mkdir_p( $dir ) ) {
			file_put_contents( "$dir/index.php", "<?php // Silence.\n" );
			file_put_contents( "$dir/.htaccess", "Require all denied\nDeny from all\n" );
		}
		return $dir;
	}

	function brickwright_meta_key( string $area ) {
		if ( class_exists( '\Bricks\Database' ) && method_exists( '\Bricks\Database', 'get_bricks_data_key' ) ) {
			return \Bricks\Database::get_bricks_data_key( $area );
		}
		return [ 'header' => '_bricks_page_header_2', 'footer' => '_bricks_page_footer_2' ][ $area ] ?? '_bricks_page_content_2';
	}

	function brickwright_is_root( $parent ) {
		return empty( $parent ) || '0' === (string) $parent;
	}

	/** Ids of the given roots and all their descendants (by parent links). */
	function brickwright_subtree_ids( array $elements, array $roots ) {
		$present  = array_column( $elements, 'id' );
		$ids      = array_values( array_intersect( $roots, $present ) );
		$children = [];
		foreach ( $elements as $e ) {
			$children[ (string) ( $e['parent'] ?? 0 ) ][] = $e['id'];
		}
		for ( $i = 0; $i < count( $ids ); $i++ ) {
			foreach ( $children[ $ids[ $i ] ] ?? [] as $c ) {
				$ids[] = $c;
			}
		}
		return $ids;
	}

	function brickwright_digest( array $elements ) {
		return hash( 'sha256', (string) wp_json_encode( array_values( $elements ) ) );
	}

	function brickwright_error_text( $error ) {
		$data = $error->get_error_data();
		return $error->get_error_message() . ( $data ? ' ' . wp_json_encode( $data ) : '' );
	}
}
