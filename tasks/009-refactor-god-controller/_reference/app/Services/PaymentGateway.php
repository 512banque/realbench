<?php

namespace App\Services;

interface PaymentGateway
{
    /**
     * Charge a token for the given amount in cents.
     *
     * @return array{status: string, transaction_id: string|null}
     */
    public function charge(int $amountCents, string $token): array;
}
