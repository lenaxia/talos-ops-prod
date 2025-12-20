<?php
/**
 * This is needed for cookie based authentication to encrypt password in
 * cookie. Needs to be 32 chars long.
 */
$cfg['blowfish_secret'] = getenv('PMA_SECRET'); /* YOU MUST FILL IN THIS FOR COOKIE AUTH! */