<?php

namespace App\Http\Resources;

use Illuminate\Http\Resources\Json\JsonResource;

class OrderResource extends JsonResource
{
    public function toArray($request): array
    {
        /** @var \App\Models\Order $order */
        $order = $this->resource;
        $payment = $order->payment;

        return [
            'order' => [
                'id' => $order->id,
                'user_id' => $order->user_id,
                'subtotal_cents' => $order->subtotal_cents,
                'tax_cents' => $order->tax_cents,
                'discount_cents' => $order->discount_cents,
                'total_cents' => $order->total_cents,
                'status' => $order->status,
            ],
            'payment' => $payment ? [
                'id' => $payment->id,
                'amount_cents' => $payment->amount_cents,
                'status' => $payment->status,
                'transaction_id' => $payment->transaction_id,
            ] : null,
        ];
    }
}
