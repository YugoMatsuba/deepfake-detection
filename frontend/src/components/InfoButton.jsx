import React, { useState } from 'react';

const InfoButton = ({ title, content }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Info Icon Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center justify-center w-5 h-5 ml-2 text-gray-500 hover:text-blue-600 transition-colors cursor-pointer"
        aria-label={`Information about ${title}`}
      >
        <svg
          className="w-5 h-5"
          fill="currentColor"
          viewBox="0 0 20 20"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Modal Popup */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setIsOpen(false)}>
          <div
            className="relative w-[500px] max-w-[90%] bg-white rounded-lg shadow-xl p-6"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close button */}
            <button
              className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 transition"
              onClick={() => setIsOpen(false)}
              aria-label="Close"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {/* Title */}
            {title && (
              <h3 className="text-lg font-semibold text-gray-900 mb-4 pr-8">
                {title}
              </h3>
            )}

            {/* Content */}
            <div className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">
              {content}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default InfoButton;
