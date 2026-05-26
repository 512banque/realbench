<?php

namespace App\Exceptions;

use Illuminate\Validation\ValidationException;
use Illuminate\Support\Facades\Validator;

class InsufficientStockException extends \RuntimeException
{
    public function render(): never
    {
        throw ValidationException::withMessages([
            'items' => [$this->getMessage()],
        ]);
    }
}
