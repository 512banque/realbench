<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreOrderRequest;
use App\Http\Resources\OrderResource;
use App\Services\OrderService;

class OrderController extends Controller
{
    public function __construct(private OrderService $orders)
    {
    }

    public function store(StoreOrderRequest $request)
    {
        $order = $this->orders->place(
            (int) $request->input('user_id'),
            $request->input('items', []),
            (string) $request->input('payment_method'),
            (string) $request->input('payment_token'),
        );

        return OrderResource::make($order)
            ->response()
            ->setStatusCode(201);
    }
}
