<?php

namespace App\Exceptions;

use Illuminate\Http\JsonResponse;

class PaymentFailedException extends \RuntimeException
{
    public function render(): JsonResponse
    {
        return new JsonResponse([
            'message' => 'Payment failed',
            'status' => 'failed',
        ], 402);
    }
}
