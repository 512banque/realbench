<?php

namespace App\Models;

use Database\Factories\ProductFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class Product extends Model
{
    /** @use HasFactory<ProductFactory> */
    use HasFactory;

    protected $fillable = [
        'name',
        'price_cents',
        'stock',
    ];

    protected $casts = [
        'price_cents' => 'integer',
        'stock' => 'integer',
    ];
}
