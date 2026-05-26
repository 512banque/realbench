<?php

namespace App\Services;

use App\Exceptions\InsufficientStockException;
use App\Models\Product;

class StockService
{
    /**
     * Reserve stock for each line. Must be called inside a transaction by
     * the caller; throws InsufficientStockException if any product has
     * insufficient stock.
     *
     * @param  array<int, array{product: Product, quantity: int}>  $lines
     */
    public function reserve(array $lines): void
    {
        foreach ($lines as $line) {
            /** @var Product $product */
            $product = $line['product'];
            $qty = (int) $line['quantity'];

            if ($product->stock < $qty) {
                throw new InsufficientStockException(
                    "Insufficient stock for product {$product->id}"
                );
            }

            $product->stock = $product->stock - $qty;
            $product->save();
        }
    }
}
