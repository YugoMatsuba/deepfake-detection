// Just a random varialbe to make sure the code works
let fakeVideoPercentage = 82;

// Basic button styling configurations
const baseButton = "justify-center items-center mt-[15px] text-[17px] font-semibold px-10 py-3.5 rounded-lg shadow"

export default function Analysis() {
    return (
        <div className="flex font-inter font-bold flex-col items-center pt-8 mt-[200px]">
            <h1 className="mt-[60px] text-4xl text-[#0D47A1] text-center">
                Initial Analysis: Synthetic Media Chance = {fakeVideoPercentage}%
            </h1>
            <h2 className="mt-[40px] text-4xl leading-none tracking-normal text-black">
                Metadata anomalies: None found
            </h2>
            <h3 className="mt-[140px] text-4xl">
                Proceed to frame analysis?
            </h3>

            <div className="flex flex-row gap-20 mt-[20px]">
                <button className={`${baseButton} bg-[#1E88E5] text-white hover:bg-[#114f85] hover:text-[#cccccc] transition-colors`}>
                    Yes
                </button>
                <button className={`${baseButton} bg-[#E0E0E0] text-[#1702028F] border border-[#1E88E5] hover:bg-[#b5b5b5] hover:text-[#02028f] transition-colors `}>
                    No
                </button> 
            </div>
        </div>
    )
}