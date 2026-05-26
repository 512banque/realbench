<?php

return [
    /*
    |--------------------------------------------------------------------------
    | Force payment status
    |--------------------------------------------------------------------------
    |
    | Set to 'failed' (e.g. via tests) to make FakePaymentGateway::charge()
    | systematically fail. Any other value (or null) keeps the default
    | successful behavior.
    |
    */
    'force_status' => env('PAYMENTS_FORCE_STATUS', 'ok'),
];
