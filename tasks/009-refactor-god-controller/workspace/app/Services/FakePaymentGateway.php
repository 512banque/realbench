<?php

namespace App\Services;

class FakePaymentGateway
{
    /**
     * Charge a token for the given amount.
     *
     * Behavior is deterministic and controlled via config('payments.force_status'):
     *   - 'failed' → returns ['status' => 'failed', 'transaction_id' => null]
     *   - anything else (default) → returns ['status' => 'ok', 'transaction_id' => 'txn_...']
     *
     * @return array{status: string, transaction_id: string|null}
     */
    public function charge(int $amountCents, string $token): array
    {
        $forced = config('payments.force_status', 'ok');

        if ($forced === 'failed' || $token === 'tok_fail') {
            return [
                'status' => 'failed',
                'transaction_id' => null,
            ];
        }

        return [
            'status' => 'ok',
            'transaction_id' => 'txn_'.bin2hex(random_bytes(6)),
        ];
    }
}
